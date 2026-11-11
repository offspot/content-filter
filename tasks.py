import pathlib
import shutil
import tempfile
import urllib.request
import zipfile

from invoke import tasks

deps_options = ("runtime", "test", "dev")
root = pathlib.Path(__file__).parent


def download_to(url, fpath):
    """poor man's wget"""
    with urllib.request.urlopen(url) as response, open(fpath, "wb") as fh:  # nosec  # noqa: S310
        fh.write(response.read())


@tasks.task
def serve(c, args=""):
    """run devel HTTP server locally. Use --args to specify additional uvicorn args"""
    with c.cd("src"):
        c.run(f"python -m uvicorn contentfilter.main:app --reload {args}", pty=True)


@tasks.task
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
