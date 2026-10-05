import os

import pytest

# TFRS needs Keras 2; this must be set before anything imports TensorFlow.
os.environ.setdefault("TF_USE_LEGACY_KERAS", "1")


@pytest.fixture(scope="session")
def spark():
    pyspark_sql = pytest.importorskip("pyspark.sql")
    session = (
        pyspark_sql.SparkSession.builder.master("local[1]")
        .config("spark.sql.shuffle.partitions", 1)
        .config("spark.ui.enabled", "false")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    yield session
    session.stop()
