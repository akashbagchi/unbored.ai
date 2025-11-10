from setuptools import setup, find_packages
from pathlib import Path

# Read requirements
requirements = []
req_file = Path(__file__).parent / "requirements.txt"
if req_file.exists():
    requirements = req_file.read_text().strip().split("\n")

setup(
    name="unbored",
    version="0.2.0",
    description="One command automated onboarding documentation generator",
    author="Akash Bagchi, Akshaya Nadathur, Pranjal Padakannaya, Sachin SS",
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'unbored me=unbored.cli:main',
        ],
    },
    include_package_data=True,
    package_data={
        'unbored': [
            'template-site/**/*',
            'template-site/**/.*'
        ],
    },
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)

