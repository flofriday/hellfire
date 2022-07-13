import argparse
from dataclasses import dataclass, field
from datetime import datetime
import os
import re
import shutil
import subprocess
from functools import lru_cache

from jinja2 import Template, select_autoescape
import toml

DATE_FORMAT = "%d %b, %Y"


def verify_setup(src: str, dst: str):
    # Check that pandoc is installed
    if not shutil.which("pandoc"):
        print(
            "🔥 Pandoc is not installed (or maybe just not in the path)\n"
            "hellfire requires pandoc, which can be installed from:\n"
            "https://pandoc.org/installing.html"
        )
        exit(1)

    # Verify the source directory is in good health
    if not os.path.isdir(src):
        raise Exception(f"The source directory `{src}` doesn't exist")

    required_files = map(
        lambda f: os.path.join(src, f),
        ["config.toml", "home.template", "post.template"],
    )
    had_error = False
    for file in required_files:
        if not os.path.exists(file):
            print(f"🔥 Required file '{file}' does not exist.")

    if had_error:
        exit(1)

    # Verify the output directory
    if not os.path.isdir(dst):
        os.mkdir(dst)


def load_config(src: str) -> dict:
    config_path = os.path.join(src, "config.toml")
    if not os.path.isfile(config_path):
        print(f"🔥 Config '{config_path}' doesn't exist.")
        exit(1)

    config = toml.load(config_path)
    if "url" not in config:
        print(f"🔥 'url' key not found in '{config_path}'")
        exit(1)

    return config


# This functions checks if a file already exists and is up to date.
def is_done(dst: str, *args: list[str]):
    if not os.path.exists(dst):
        return False

    dst_mtime = os.path.getmtime(dst)
    for src in args:
        src_mtime = os.path.getmtime(src)
        if dst_mtime < src_mtime:
            return False

    return True


# Copies all files (shallow copy) from the src to the dst, excluding the
# exceptions
# Note: So when you do this once all static files will be copied. However, if
# you now delete a file from the blog, it will be still in the destination
# folder. So maybe we need to track these static files, or we just skillfully
# ignore this problem.
def copy_files(src: str, dst: str, exceptions: list[str] = None):
    if exceptions is None:
        exceptions = []

    files = os.listdir(src)
    files = filter(lambda f: os.path.isfile(os.path.join(src, f)), files)
    files = filter(lambda f: f not in exceptions, files)

    for file in files:
        src_path = os.path.join(src, file)
        dst_path = os.path.join(dst, file)

        if is_done(dst_path, src_path):
            continue

        shutil.copyfile(src_path, dst_path)


@dataclass
class PostMetadata:
    title: str = None
    date: datetime = None
    description: str = None
    image: str = None
    other: dict[str, str] = field(default_factory=dict)


# This is a very simple frontmatter parser, it only supports simple yaml key
# value attributes.
@lru_cache(maxsize=512)
def load_post_metadata(src: str, post: str, base_url) -> PostMetadata:
    post_path = os.path.join(src, "posts", post, "post.md")
    with open(post_path) as md:
        # TODO: read the lines lazy
        lines = map(lambda l: l.strip(), md.readlines())

    meta = PostMetadata()
    other = {}
    in_frontmatter = False
    for line in lines:
        # Parse the data
        if line == "---":
            if in_frontmatter:
                break
            in_frontmatter = True
            continue

        if not in_frontmatter:
            break

        key, value = line.split(":")
        key = key.strip()
        value = value.strip()

        # Store the data
        if key == "date":
            meta.date = datetime.strptime(value, "%Y-%m-%d")
        elif key == "title":
            meta.title = value
        elif key == "description":
            meta.description = value
        elif key == "image":
            if not value.startswith("https://"):
                value = base_url + f"/posts/{post}/{value}"
            meta.image = value
        else:
            other[key] = value

    # Fill in the blanks with warnings
    if meta.title is None:
        # TODO: take the filename
        meta.title = "No title available"
        print(f"⚠️ Post '{post_path}' doesn't have a title in the metadata.")

    if meta.date is None:
        meta.date = datetime.fromtimestamp(os.path.getmtime(post_path))
        print(f"⚠️ Post '{post_path}' doesn't have a date in the metadata.")

    if meta.description is None:
        # TODO: We could parse the text and add the start of the post by default
        meta.description = ""
        print(f"⚠️ Post '{post_path}' doesn't have a description in the metadata.")

    if meta.image is None:
        # We should by default link to the profile picture or something
        meta.image = ""
        print(f"⚠️ Post '{post_path}' doesn't have a image in the metadata.")

    return meta


def compile_home(src: str, dst: str, config: dict):
    @dataclass
    class PostPreview:
        title: str
        date: str
        url: str

    template_path = os.path.join(src, "home.template")
    index_path = os.path.join(dst, "index.html")

    # Iterate over all posts and create a list to which we can link.
    posts = os.listdir(os.path.join(src, "posts"))
    posts = filter(lambda p: os.path.isdir(os.path.join(src, "posts", p)), posts)

    previews = []
    for post in posts:
        meta = load_post_metadata(src, post, config["url"])

        preview = PostPreview(
            meta.title, datetime.strftime(meta.date, DATE_FORMAT), "posts/" + post + "/"
        )
        previews.append(preview)

    previews.sort(key=lambda p: p.date)

    with open(template_path) as home:
        template = Template(
            home.read(),
            autoescape=select_autoescape(
                enabled_extensions=("html", "xml"),
                default_for_string=True,
            ),
        )

    with open(index_path, "w") as index:
        index.write(template.render(previews=previews))

    # Also copy all files that are not templates into the root of the dst
    # directory so that static images will be served and can be used in the
    # templates
    copy_files(src, dst, exceptions=["home.template", "post.template", "config.toml"])


def compile_post(post: str, template: Template, src: str, dst: str, config: dict):
    # Also copy all files from the dir to dst
    post_dir = os.path.join(src, "posts", post)
    html_dir = os.path.join(dst, "posts", post)
    post_path = os.path.join(post_dir, "post.md")
    html_path = os.path.join(html_dir, "index.html")
    template_path = os.path.join(src, "post.template")

    if not os.path.isdir(html_dir):
        os.mkdir(html_dir)
    copy_files(post_dir, html_dir, exceptions=["post.md"])

    # Skip html if already up to date (this is expensive)
    if is_done(html_path, post_path, template_path):
        return

    # Compile the markdown to html
    pandoc = subprocess.run(
        [
            "pandoc",
            "--from",
            "gfm",
            "--to",
            "html",
            post_path,
        ],
        # shell=True,
        capture_output=True,
        text=True,
    )

    if pandoc.returncode != 0:
        print(
            f"🔥 '{' '.join(pandoc.args)}' failed with error code {pandoc.returncode}\n"
            "Visit this for more information: https://pandoc.org/MANUAL.html#exit-codes\n"
            "Pandocs error: ",
            pandoc.stderr,
        )
        return

    # Write the complete document
    meta = load_post_metadata(src, post, config["url"])
    with open(html_path, "w") as f:
        f.write(
            template.render(
                content=pandoc.stdout,
                title=meta.title,
                description=meta.description,
                image=meta.image,
                date=datetime.strftime(meta.date, DATE_FORMAT),
            )
        )


def compile_posts(src: str, dst: str, config: dict):
    dst_path = os.path.join(dst, "posts")
    if not os.path.isdir(dst_path):
        os.mkdir(dst_path)

    template_path = os.path.join(src, "post.template")
    with open(template_path) as home:
        template = Template(
            home.read(),
            autoescape=select_autoescape(
                enabled_extensions=("html", "xml"),
                default_for_string=True,
            ),
        )

    posts = os.listdir(os.path.join(src, "posts"))
    posts = filter(lambda p: os.path.isdir(os.path.join(src, "posts", p)), posts)
    for post in posts:
        compile_post(post, template, src, dst, config)


def build(args):
    # Delete everything in a clean build
    if args.clean and os.path.exists(args.out):
        shutil.rmtree(args.out)

    # Setup and verify the conditions
    verify_setup(args.source, args.out)

    # Load the config.toml file
    config = load_config(args.source)

    # Compile the homepage
    compile_home(args.source, args.out, config)

    # Compile all posts
    compile_posts(args.source, args.out, config)


def new_post(args):
    # Create all used variables
    title = args.title
    date = datetime.now().strftime("%Y-%m-%d")
    whitespace_pattern = re.compile("(\s|-)+")
    path_pattern = re.compile("[^a-zA-Z0-9\-]+")
    title_path = whitespace_pattern.sub("-", title)
    title_path = path_pattern.sub("", title_path)
    title_path = title_path.lower()
    print(f"'{title_path}'")

    # Create the directory
    dir_path = os.path.join(args.source, "posts", title_path)
    os.mkdir(dir_path)

    with open(os.path.join(dir_path, "post.md"), "w") as f:
        f.write(
            f"""
---
title: {title}
date: {date}
image: some_image_for_social_preview.png
description: This is just a new post.
---

<!-- Start writing your markdown here ;) -->
""".strip()
        )


def main():
    # Parse the arguments
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build the website.")
    build_parser.add_argument(
        "source", default=".", nargs="?", help="The source directory of the blog."
    )
    build_parser.add_argument(
        "--out", default="./dist", help="The directory to store the generated pages in."
    )
    build_parser.add_argument(
        "--clean",
        action="store_true",
        help="Make a clean build (slow), however it will ensure that no old artifacts will leak.",
    )

    new_parser = subparsers.add_parser("new", help="Create a new post.")
    new_parser.add_argument("title", help="The title of the new post.")
    new_parser.add_argument(
        "source", default=".", nargs="?", help="The source directory of the blog."
    )

    args = parser.parse_args()

    if args.command == "build":
        build(args)
    elif args.command == "new":
        new_post(args)


if __name__ == "__main__":
    main()
