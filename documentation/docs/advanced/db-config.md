# Advanced Database Configuration

**Updated in v0.27.0**

!!! warning
    This is a recently released experimental feature. Running any trading bots without manual supervision may incur additional risks. It is imperative that you thoroughly understand and test the strategy and parameters before deploying bots that can trade in an unattended manner.

Hummingbot uses SQLite for database by default, but it may be limiting for some cases such as sharing data to external system, in some cases user may want to use their own preferred client/server RDBMS for it.

Other RDBMS are supported on Hummingbot through SQLAlchemy, it has [included some widely used RDBMS dialects](https://docs.sqlalchemy.org/en/13/dialects/index.html), i.e.:

* PostgreSQL
* MySQL
* Oracle
* Microsoft SQL Server

These dialects requires separate DBAPI driver to be installed on Hummingbot's conda environment, see [SQLAlchemy documentation](https://docs.sqlalchemy.org/en/13/dialects/index.html) for more information on appropriate DBAPI driver for each RDBMS. For example, to use PostgreSQL, `psycopg2` need to be installed. Run the following command to install it using conda:
```
conda install psycopg2
```
To configure RDBMS connection, we need to edit `conf_global.yml` in `/conf` directory.

```
# Advanced database options, currently supports SQLAlchemy's included dialects
# Reference: https://docs.sqlalchemy.org/en/13/dialects/

db_engine: sqlite
db_host: 127.0.0.1
db_port: '3306'
db_username: username
db_password: password
db_name: dbname
```

## Configuration Parameters

| Configuration Parameter | Possible Values |
|---|---|
| db_engine |`sqlite`<br />`postgres`<br />`mysql`<br />`oracle`<br />`mssql`|
| db_host | any string e.g. `127.0.0.1` |
| db_port | any string e.g. `3306` |
| db_username | any string e.g. `username` |
| db_password | any string e.g. `password` |
| db_name | any string e.g. `dbname` |
</div>

## External SQLAlchemy Dialects
It is also possible to connect with available SQLAlchemy's external dialects (e.g. Amazon Redshift). But the feature is not currently supported in Hummingbot due to its various DSN format, **use this at your own risk**.

<style>
.md-typeset__table {
  min-width: 100%;
}
table {
  width: 100%;
}
</style>

<small>*Feature contribution by [Rupiah Token](https://rupiahtoken.com).*</small>