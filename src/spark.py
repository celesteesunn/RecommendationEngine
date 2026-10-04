"""Create the local Spark session shared by the data and feature jobs."""

from pathlib import Path

from pyspark.sql import SparkSession


def create_spark(config: dict, app_name: str) -> SparkSession:
    spark_config = config["spark"]
    local_dir = Path(spark_config["local_dir"]).expanduser()
    local_dir.mkdir(parents=True, exist_ok=True)
    return (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.driver.memory", spark_config["driver_memory"])
        .config("spark.sql.shuffle.partitions", spark_config["shuffle_partitions"])
        .config("spark.local.dir", str(local_dir))
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
