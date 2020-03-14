# infrastructure

## deployment

1. [install ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html)
2. setup [ansible inventory](https://docs.ansible.com/ansible/latest/user_guide/intro_inventory.html)

   it should look something like:

   `/etc/ansible/hosts`

   ```yaml
   ---
   all:
     children:
       kodiak_prod:
         hosts:
           kodiak_prod_app_server:
             ansible_host: 255.255.255.255
             ansible_user: root
             ansible_python_interpreter: /usr/bin/python3

           kodiak_prod_ingestor:
             ansible_host: 255.255.255.255
             ansible_user: root
             ansible_python_interpreter: /usr/bin/python3

       kodiak_staging:
         hosts:
           kodiak_staging_ingestor:
             ansible_host: 255.255.255.255
             ansible_user: root
             ansible_python_interpreter: /usr/bin/python3

           kodiak_prod_app_server:
             ansible_host: 255.255.255.255
             ansible_user: root
             ansible_python_interpreter: /usr/bin/python3
   ```

3. run the playbook for the specified service (see below)

### dashboard

Note: while the docker containers for the specific git sha are downloaded and
deployed, the templates for the systemd crons are copied directly from your git
repo. Make sure your local changes are in order!

```shell
# /kodiak
# note: when deploying to prod, don't forget to change the target
ansible-playbook -e 'target=kodiak_staging_ingestor' infrastructure/playbooks/dashboard-deploy.yml
```
