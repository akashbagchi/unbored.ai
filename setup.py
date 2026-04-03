from setuptools import setup, find_packages
from pathlib import Path

# Read requirements
requirements = []
req_file = Path(__file__).parent / "requirements.txt"
if req_file.exists():
    requirements = req_file.read_text().strip().split("\n")

setup(
    name="unbored",
    version="0.5.1",
    description="One command automated onboarding documentation generator",
    author="Akash Bagchi, Akshaya Nadathur, Pranjal Padakannaya, Sachin SS",
    packages=find_packages(),
    install_requires=requirements,
    extras_require={
        "dev": ["pytest>=7.0", "pytest-mock>=3.0"],
    },
    entry_points={
        "console_scripts": [
            "unbored=unbored.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "unbored": ["template-site/**/*", "template-site/**/.*"],
    },
    python_requires=">=3.8,<4.0",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
