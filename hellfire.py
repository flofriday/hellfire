import argparse
from dataclasses import dataclass
import os
import shutil
import subprocess

from jinja2 import Template


def verify_setup(src: str, dst: str):
    if not os.path.isdir(src):
        raise Exception(f"The source directory `{src}` doesn't exist")

    # TODO: more tests that the templates and posts exist

    if not os.path.isdir(dst):
        os.mkdir(dst)


# This functions checks if a file already exists and is up to date.
def is_done(src: str, dst: str):
    if not os.path.exists(dst):
        return False

    src_mtime = os.path.getmtime(src)
    dst_mtime = os.path.getmtime(dst)

    return dst_mtime > src_mtime


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

        if is_done(src_path, dst_path):
            continue

        shutil.copyfile(src_path, dst_path)


# This is a very simple frontmatter parser, it only supports simple yaml key
# value attributes.
def parse_frontmatter(src: str) -> dict[str, str]:
    with open(src) as md:
        lines = map(lambda l: l.strip(), md.readlines())

    frontmatter = {}
    in_frontmatter = False
    for line in lines:
        if line == "---":
            if in_frontmatter:
                break
            in_frontmatter = True
            continue

        if not in_frontmatter:
            break

        key, value = line.split(":")
        frontmatter[key] = value

    return frontmatter


def compile_home(src: str, dst: str):
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
        post_path = os.path.join(src, "posts", post, "post.md")
        date = os.path.getctime(post_path)
        meta = parse_frontmatter(post_path)
        if "date" not in meta:
            print(f"⚠️ File {post_path} doesn't have a date frontmatter attribue")
        else:
            date = meta["date"]

        preview = PostPreview(post, date, "posts/" + post + "/")
        previews.append(preview)

    previews.sort(key=lambda p: p.date)

    with open(template_path) as home:
        template = Template(home.read())

    with open(index_path, "w") as index:
        index.write(template.render(previews=previews))

    # Also copy all files that are not templates into the root of the dst
    # directory so that static images will be served and can be used in the
    # templates
    copy_files(src, dst, exceptions=["home.template", "post.template"])


def compile_posts(src: str, dst: str, force_build: bool = False):
    dst_path = os.path.join(dst, "posts")
    if not os.path.isdir(dst_path):
        os.mkdir(dst_path)

    template_path = os.path.join(src, "post.template")
    with open(template_path) as home:
        template = Template(home.read())

    posts = os.listdir(os.path.join(src, "posts"))
    posts = filter(lambda p: os.path.isdir(os.path.join(src, "posts", p)), posts)
    for post in posts:
        # Also copy all files from the dir to dst
        post_dir = os.path.join(src, "posts", post)
        html_dir = os.path.join(dst, "posts", post)
        post_path = os.path.join(post_dir, "post.md")
        html_path = os.path.join(html_dir, "index.html")

        if not os.path.isdir(html_dir):
            os.mkdir(html_dir)
        copy_files(post_dir, html_dir, exceptions=["post.md"])

        # Skip if is already newest
        # TODO: we should also include the template timestamp
        if is_done(post_path, html_path) and not force_build:
            continue

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
        # print(" ".join(pandoc.args))

        if pandoc.returncode != 0:
            print(
                f"🔥 '{' '.join(pandoc.args)}' failed with error code {pandoc.returncode}\n"
                "Visit this for more information: https://pandoc.org/MANUAL.html#exit-codes\n"
                "Pandocs error: ",
                pandoc.stderr,
            )
            continue

        # Write the complete document
        with open(html_path, "w") as f:
            f.write(template.render(content=pandoc.stdout))


def main():
    # Parse the arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "source", default=".", nargs="?", help="The source directory of the blog."
    )
    parser.add_argument(
        "--out", default="./dist", help="The directory to store the generated pages in."
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Make a clean build (slow), however it will ensure that no old artifacts will leak.",
    )
    args = parser.parse_args()

    # Delete everything in a clean build
    if args.clean:
        shutil.rmtree(args.out)

    # Setup and verify the conditions
    verify_setup(args.source, args.out)

    # Compile the homepage
    compile_home(args.source, args.out)

    # Compile all posts
    compile_posts(args.source, args.out)


if __name__ == "__main__":
    main()
