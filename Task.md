Task: Support multiple credentials for a connector
Description:
Hummingbot supports one credential per connector.

Credentials gets saved at path conf/connectors/<connector_name>.yml

If conf/connectors/<connector_name>_<suffix>.yml present, ignored by hummingbot

Concept of Master and Sub-account

When “connect <exchange>” it should take type as well as parameter

If sub-account, master/parent account name to be defined

credentials file can be of form conf/connectors/<connector_name>:<acc_name>.yml

Check for places that can be affected like:

“balance” command needs to give balance for all accounts and creds present

Strategies need to define account name when running, if not defined, default cred will be picked up
