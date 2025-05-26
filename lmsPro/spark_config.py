from pyspark.sql import SparkSession

def get_spark_session():
    return SparkSession.builder \
        .appName("DjangoSparkApp") \
        .master("spark://spark:7077") \
        .config("spark.driver.host", "web") \
        .config("spark.driver.bindAddress", "0.0.0.0") \
        .config("spark.executor.memory", "1g") \
        .config("spark.driver.memory", "1g") \
        .getOrCreate() 