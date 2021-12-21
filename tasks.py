import io
import pathlib
import shutil
import sys
import tempfile
import zipfile
import urllib.request

from invoke import task

deps_options = ("runtime", "test", "dev")
root = pathlib.Path(__file__).parent


def download_to(url, fpath):
    """poor man's wget"""
    with urllib.request.urlopen(url) as response, open(fpath, "wb") as fh:  # nosec
        fh.write(response.read())


@task
def install_deps(c, package=deps_options[0]):
    """install dependencies for runtime (default) or extra packages

    packages:
        - runtime: default, to run the contentfilter
        - test: to run the test suite
        - dev: all deps to develop the contentfilter"""
    if package not in deps_options:
        print(
            f"Invalid deps package `{package}`. Choose from: {','.join(deps_options)}"
        )
        sys.exit(1)

    try:
        import toml
    except ImportError:
        c.run("pip install toml>=0.10.2")
        import toml

    packages = []
    manifest = toml.load("pyproject.toml")
    # include deps from required package and previous ones in list
    for option in deps_options[: deps_options.index(package) + 1]:
        packages += manifest["dependencies"][option]

    c.run(
        "pip install -r /dev/stdin",
        in_stream=io.StringIO("\n".join(packages)),
    )


@task
def serve(c, args=""):
    """run devel HTTP server locally. Use --args to specify additional uvicorn args"""
    with c.cd("src"):
        c.run(f"python -m uvicorn contentfilter.main:app --reload {args}", pty=True)


@task
def download_js(c):
    assets_fpath = root / "src/contentfilter/assets"
    bs_version = "5.1.3"
    bsi_version = "1.7.1"

    with tempfile.TemporaryDirectory() as tmp_dir:
        # bootstrap
        bs_asset_dir = assets_fpath.joinpath(f"bootstrap-{bs_version}")
        if bs_asset_dir:
            shutil.rmtree(bs_asset_dir, ignore_errors=True)

        print(f"Downloading Bootstrap {bs_version} into {bs_asset_dir}")

        bszip_fpath = pathlib.Path(tmp_dir) / "bootstrap.zip"
        download_to(
            f"https://github.com/twbs/bootstrap/releases/download/v{bs_version}/"
            f"bootstrap-{bs_version}-dist.zip",
            bszip_fpath,
        )
        with zipfile.ZipFile(bszip_fpath, "r") as bszip:
            bszip.extractall(path=assets_fpath)

        # rename target folder
        assets_fpath.joinpath(f"bootstrap-{bs_version}-dist").rename(bs_asset_dir)

        # bootstrap-icons
        bsi_asset_dir = assets_fpath.joinpath(f"bootstrap-icons-{bsi_version}")
        if bs_asset_dir:
            shutil.rmtree(bsi_asset_dir, ignore_errors=True)
        print(f"Downloading Bootstrap-icons {bsi_version} into {bsi_asset_dir}")

        bsizip_fpath = pathlib.Path(tmp_dir) / "bootstrap-icons.zip"
        download_to(
            f"https://github.com/twbs/icons/releases/download/v{bsi_version}/"
            f"bootstrap-icons-{bsi_version}.zip",
            bsizip_fpath,
        )
        with zipfile.ZipFile(bsizip_fpath, "r") as bsizip:
            bsizip.extractall(path=assets_fpath)

        download_to(
            f"https://cdn.jsdelivr.net/npm/bootstrap-icons@{bsi_version}/"
            "font/bootstrap-icons.css",
            bsi_asset_dir / "bootstrap-icons.css",
        )
