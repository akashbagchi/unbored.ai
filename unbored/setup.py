from setuptools import setup, find_packages

setup(
        name="ghost-onboarder",
        version="0.1.0",
        packages=find_packages(),
        install_requires=open('requirements.txt').read().splitlines(),
        entry_points={
            'console_scripts': [
                'ghost-onboarder=cli.main:app',
                ],
            },
        )
