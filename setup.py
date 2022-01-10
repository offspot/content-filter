import pathlib
import sys

try:
    import toml
except ImportError:
    print("Please install `toml` to use setup.py")
    sys.exit(1)
from setuptools import find_packages, setup

here = pathlib.Path(__file__).resolve().parent
manifest = toml.load(here / "pyproject.toml")
package_path = pathlib.Path("./src/contentfilter")

metadata = dict()
with open(package_path / "__init__.py", "r") as fh:
    exec(fh.read(), metadata)  # pylint: disable=W0122


with open(here / "README.md", "r") as fh:
    long_desc = fh.read()


def recursive_glob(glob):
    return [str(path.relative_to(package_path)) for path in package_path.glob(glob)]


setup(
    name=metadata["__title__"],
    version=metadata["__version__"],
    url="https://github.com/offspot/content-filter",
    description=metadata["__description__"],
    author="Offspot Team",
    author_email="dev@kiwix.org",
    maintainer="Offspot Team",
    maintainer_email="dev@kiwix.org",
    long_description=long_desc,
    long_description_content_type="text/markdown",
    license="GPL-3.0-or-later",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
    ],
    packages=find_packages("src"),
    package_dir={"": "src"},
    package_data={
        "contentfilter": [
            *recursive_glob("./assets/**/*"),
            *recursive_glob("./templates/**/*"),
        ]
    },
    python_requires=">=3.8",
    install_requires=manifest["dependencies"]["runtime"],
    tests_require=manifest["dependencies"]["test"],
    extras_require={
        "test": manifest["dependencies"]["test"],
        "dev": manifest["dependencies"]["dev"],
    },
    zip_safe=False,
)
