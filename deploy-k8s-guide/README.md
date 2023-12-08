# Deploy hummingbot on Kubernetes

## 1. Deploy hummingbot (used for CEX)  
This is guide to deploy simple market making strategy in Bing X CEX with spot trading-pair AURA-USDT

- un-comment command in sts.yaml to make pod sleep
```
command: [ "/bin/bash", "-c", "--" ]
args: [ "while true; do sleep 30; done;" ]
```
- apply secret-password.yaml, secret-pull-image.yaml, configmap.yaml and sts.yaml
```sh
kubectl apply -f secret-password.yaml
kubectl apply -f secret-pull-image.yaml
kubectl apply -f configmap.yaml
kubectl apply -f sts.yaml
```
- exec to pod to setup password, create env
```sh
kubectl exec aura-usdt-bing-x-hummingbot-0 -it bash 
mkdir /home/hummingbot/conf/connectors
conda activate hummingbot
python ./bin/hummingbot.py
# follow step to create password

```
- inside hummingbot terminal, connect bing x with api key and secret key
```
connect bing_x
# enter api key and secret key, if success, screen will display "You are connected to bing_x."
```
- write password to secret-password.yaml file and apply it
```sh
kubectl apply -f secret-password.yaml
```
- comment command in sts.yaml to make pod run automatically, then apply it:
```sh
# comment this is sts.yaml
# command: [ "/bin/bash", "-c", "--" ]
# args: [ "while true; do sleep 30; done;" ]

kubectl apply -f sts.yaml
```

## 2. Deploy gateway (used for DEX)

- apply resource:
```sh
kubectl apply -f secret-passphrase-gateway.yaml
kubectl apply -f sts-gateway.yaml
```

- generate certs from hummingbot
```sh
kubectl exec aura-usdt-bing-x-hummingbot-0 -it bash
conda activate hummingbot
python ./bin/hummingbot.py
# login to hummingbot
# generate certs with passphrase
gateway generate-certs
```

- copy certs from hummingbot to gateway
```sh
kubectl cp aura-usdt-bing-x-hummingbot-0:/home/hummingbot/certs certs
kubectl cp certs halotrade-gateway-hummingbot-0:/home/gateway

# update passphrase secret then apply again
kubectl apply -f secret-passphrase-gateway.yaml
```

- create config in gateway
```sh
kubectl exec halotrade-gateway-hummingbot-0 -it bash
chmod a+x gateway-setup.sh
./gateway-setup.sh
# Do you want to copy over client certificates (Y/N) >>> N
```

- comment sleep command in sts-gateway, then apply again