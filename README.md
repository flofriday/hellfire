# hellfire

My personal static site generator for my blog,
based on python, pandoc and jinja.

This is mostly tailored for my usecase, and is also just a challenge for me to
hack on. Also, there was some frustration with some other static site
generators, in that I want to be each blog post to be its own folder with a
simple markdown file its static assets. But also if a blogpost had some code
or notes associated with it, I could simply drop them in there.

## Status

I am not currently using this software at the moment. However, it is already
useable (even though it is very rough around the edges).

Here are some features I want to implement in the future:

- [ ] Build in server for development with auto reloading
      (if a file updates, a rebuild should be triggered, and reload the browser)
- [ ] Improved CLI UX
- [ ] Propper frontmatter parsing
- [ ] Semantic error handling
      (if the markdown points to an image that doesn't exist it should display a warning)

## Usage

You need a local installation of Python 3.10 and pip.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python hellfire.py example/
```
