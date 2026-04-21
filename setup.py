from setuptools import setup, find_packages

# 1. NEW PACKAGE NAME (Must be unique on PyPI)
pkg_name = "qobuz-dl-ultimate"

def read_file(fname):
    # Added encoding="utf-8" to prevent build errors with emojis in README
    with open(fname, "r", encoding="utf-8") as f:
        return f.read()

requirements = [
    "pathvalidate",
    "requests",
    "mutagen",
    "tqdm",
    "pick==1.6.0",
    "beautifulsoup4",
    "colorama",
    # NOTE: cryptography was used in the original downloader, keeping it for safety
    "cryptography", 
]

setup(
    name=pkg_name,
    # 2. VERSION RESET FOR YOUR RELEASE
    version="1.7.0",  
    # 3. AUTHOR INFO
    author="Riccardo (Sei969)",
    author_email="Sei969@users.noreply.github.com",
    description="The Ultimate Lossless and Hi-Res music downloader for Qobuz with ReplayGain and Classical metadata",
    long_description=read_file("README.md"),
    long_description_content_type="text/markdown",
    # 4. LINK TO YOUR FORK
    url="https://github.com/Sei969/qobuz-dl", 
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            # Keeping the original command names for backward compatibility
            "qobuz-dl = qobuz_dl:main",
            "qdl = qobuz_dl:main",
        ],
    },
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)