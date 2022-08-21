from setuptools import setup

setup(
    name="hellfire",
    py_modules=["hellfire"],
    install_requires=[
        "Jinja2",
        "toml",
        "watchdog",
    ],
    entry_points="""
        [console_scripts]
        hellfire=hellfire:main
    """,
)
