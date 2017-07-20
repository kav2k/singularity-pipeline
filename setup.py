from setuptools import setup

setup(
    name='singularity-pipeline',
    version='0.1',
    description='A runner script for pipelines using Singularity containers',
    url='https://c4science.ch/diffusion/2915/browse/master/UniBe/',
    author='Alexander Kashev',
    author_email='alexander.kashev@math.unibe.ch',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3'
    ],
    keywords='singularity container runner',
    packages=['singularity_pipeline'],
    install_requires=['PyYAML>=3.12', 'argparse>=1.4.0'],
    entry_points={
        'console_scripts': [
            'singularity-pipeline = singularity_pipeline.pipeline:__main'
        ]
    }
)
