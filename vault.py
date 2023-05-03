from aws_cdk import (
    core,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_elasticloadbalancingv2 as elbv2,
)

class VaultClusterStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Create a VPC with two subnets (one public and one private)
        vpc = ec2.Vpc(self, "VaultVpc", max_azs=2)

        # Create an ECS cluster
        cluster = ecs.Cluster(self, "VaultCluster", vpc=vpc)

        # Define the task definition for the Vault server
        vault_task_definition = ecs.TaskDefinition(
            self,
            "VaultTaskDef",
            compatibility=ecs.Compatibility.EC2,
            network_mode=ecs.NetworkMode.AWS_VPC,
            cpu="1024",
            memory_mib="2048",
        )

        # Add a container to the task definition
        container = vault_task_definition.add_container(
            "vault",
            image="vault",
            cpu=1024,
            memory_reservation_mib=512,
            environment={
                "VAULT_API_ADDR": "http://0.0.0.0:8200",
                "VAULT_DEV_ROOT_TOKEN_ID": "root",
            },
        )

        # Define a security group for the Vault servers
        vault_security_group = ec2.SecurityGroup(
            self, "VaultSecurityGroup", vpc=vpc, allow_all_outbound=True
        )
        vault_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block), connection=ec2.Port.tcp(8200)
        )

        # Launch a service with one task for the Vault server
        vault_service = ecs.FargateService(
            self,
            "VaultService",
            cluster=cluster,
            task_definition=vault_task_definition,
            assign_public_ip=True,
            security_group=vault_security_group,
        )

        # Create a load balancer to route traffic to the Vault servers
        lb = elbv2.ApplicationLoadBalancer(
            self,
            "VaultLoadBalancer",
            vpc=vpc,
            internet_facing=True,
        )
        listener = lb.add_listener(
            "VaultListener",
            port=443,
        )

        # Add the Vault service to the load balancer target group
        listener.add_targets(
            "VaultTargets",
            port=8200,
            targets=[vault_service.load_balancer_target(
                container_name="vault",
                container_port=8200,
            )],
            health_check=elbv2.HealthCheck(
                path="/v1/sys/health",
                interval=core.Duration.seconds(30),
                timeout=core.Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3,
            ),
        )
