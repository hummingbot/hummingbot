# Setup a Cloud Server

Using Hummingbot as a long running service can be achieved with the help of cloud platforms such as Google Cloud Platform, Amazon Web Services, and Microsoft Azure. You may read our blog about running [Hummingbot on different cloud providers](https://www.hummingbot.io/blog/2019-06-cloud-providers/).

As of **version 0.28.0** installing Docker takes up around 500 MB of storage space and 4 GB for Hummingbot Docker image. We tested to install and run Hummingbot on these free to lowest machine types.

| Provider | Instance Type | Instance Details |
|---------|-----------|-----------|
| Google Cloud Platform <img width=50/> | g1-small <img width=100/> | 1 vCPU, 1.7 GB memory <img width=100/> |
| Amazon Web Services | t2.micro | 1 vCPU, 1 GB memory |
| Microsoft Azure | Standard_D2s_v3 | 2 vCPU, 8 GB memory |

These instances are pre-loaded with system files that takes up around 1.2 GB so we recommend having at least **8 GB of storage space** in your cloud server.

!!! note "Exception for celo-arb strategy"
      Running a [Celo Arbitrage](/strategies/celo-arb/) strategy requires a minimum of `t2.medium` AWS instance type for improved performance.

Below, we show you how to set up a new Virtual Machine Instance on each major cloud platform.

## Google Cloud Platform

1. Log in to your Google account at https://console.cloud.google.com/
1. From the navigation menu, go to **Computer Engine** then **VM instances**
</br></br>
![](/assets/img/GCP_1.png)
1. **Change** boot disk to Ubuntu 18.04 LTS
</br></br>
![Create New Instance](/assets/img/gcp-new-vm.png)
1. You can modify the storage disk space according to preference in the same page
</br></br>
![](/assets/img/GCP_2.png)
1. When the instance is created, click **SSH** to connect to the cloud instance
</br></br>
![Connect SSH](/assets/img/gcp-ssh.png)

## Amazon Web Services

1. Log in to your AWS account at https://aws.amazon.com/console/
1. From the EC2 Dashboard, click **Launch Instance**
</br></br>
![Create New Instance](/assets/img/AWS_1.png)
1. Search and select "Ubuntu Server 18.04 LTS (HVM)"
</br></br>
![](/assets/img/AWS_2.png)
1. To modify the storage disk space, click **Add Storage** or you can skip this step
1. Click **Review and Launch**
</br></br>
![](/assets/img/AWS_3.png)
1. Select **Create a new key pair** if you don't have one yet or **Choose an existing key pair** then click **Launch Instance**
</br></br>
![](/assets/img/AWS_4.png)

### Other helpful resources

- [Connect to Your Amazon EC2 Instance](https://docs.aws.amazon.com/quickstarts/latest/vmlaunch/step-2-connect-to-instance.html)
- [Connecting to your Linux instance from Windows using PuTTY](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/putty.html)


## Microsoft Azure

1. Log in to your Microsoft account at https://portal.azure.com/
1. Go to **Virtual Machines** and click **Add** or **Create virtual machine**
</br></br>
![](/assets/img/Azure_0.png)
![](/assets/img/Azure_1.png)
1. Fill out all required fields
</br></br>
![](/assets/img/Azure_2.png)
1. Select Ubuntu Server 18.04 LTS for **Image**
1. Select **Size** to Standard_D2s_v3 - 2 vcpus, 8 GiB memory (lowest recommended size by image publisher)
1. For **Authentication type** drop-down you can use either your SSH public key or set a password instead when connecting
</br></br>
![](/assets/img/Azure_3.png)
![](/assets/img/Azure_4.png)
1. To modify the storage disk space, click **Next : Disks >** or skip this step
1. Click **Review + create** to create VM instance

### Other helpful resources

- [Connect to a Linux-based VM](https://docs.microsoft.com/en-us/azure/marketplace/partner-center-portal/create-azure-vm-technical-asset#connect-to-a-linux-based-vm)

---
# Next: [Install Hummingbot for Linux](/installation/docker/linux)
