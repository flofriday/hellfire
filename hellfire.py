import argparse
import os

from jinja2 import Template


def verify_setup(src: str, dst: str):
    if not os.path.isdir(src):
        raise Exception(f"The source directory `{src}` doesn't exist")

    # TODO: more tests that the templates and posts exist

    if not os.path.isdir(dst):
        os.mkdir(dst)


# This functions checks if a file already exists and is up to date.
def is_compiled(temp: str, out: str):
    if not os.path.exists(out):
        return False

    temp_mtime = os.path.getmtime(temp)
    out_mtime = os.path.getmtime(out)

    return out_mtime > temp_mtime


def compile_home(src: str, dst: str):
    template_path = os.path.join(src, "home.template")
    index_path = os.path.join(dst, "index.html")

    # TODO: we cannot do this for the home page as it also needs updating
    # if a post changes as it has a list of all posts.
    # Skip if the current file was already compiled
    if is_compiled(template_path, index_path):
        return

    # TODO: iterate over all posts and create a list to which we can link.

    with open(template_path) as home:
        template = Template(home.read())

    with open(index_path, "w") as index:
        index.write(template.render(name="<b>Flo</b>tschi"))

    # TODO: Also copy all files that are not templates into the root of the dst
    # directory so that static images will be served and can be used in the
    # templates


def compile_posts(src: str, dst: str):
    pass


def main():
    # Parse the arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "source", default=".", nargs="?", help="The source directory of the blog."
    )
    parser.add_argument(
        "--out", default="./dist", help="The directory to store the generated pages in."
    )
    args = parser.parse_args()

    # Setup and verify the conditions
    verify_setup(args.source, args.out)

    # Compile the homepage
    compile_home(args.source, args.out)

    # Compile all posts
    compile_posts(args.source, args.out)


if __name__ == "__main__":
    main()
