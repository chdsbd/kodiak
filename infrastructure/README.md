# infrastructure

## deployment

1. install ansible <https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html>
2. run the playbook for the specified service

### dashboard

Note: while the docker containers for the specific git sha a downloaded and
deployed, the templates for the systemd crons are copied directly from the git
repo. Make sure your local changes are in order.

```shell
# /kodiak
# note: when deploying to prod, don't forget to change the target
ansible-playbook -e 'target=kodiak_staging_ingestor' --check infrastructure/playbooks/dashboard-deploy.yml 
```
