from setuptools import setup, find_packages

setup(
    name="lokilens",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.109.2",
        "uvicorn>=0.27.1",
        "python-dotenv>=1.0.1",
        "requests>=2.31.0",
        "openai>=1.12.0",
        "python-multipart>=0.0.9",
        "pydantic>=2.6.1",
        "sseclient-py>=1.8.0",
    ],
    python_requires=">=3.11",
) 