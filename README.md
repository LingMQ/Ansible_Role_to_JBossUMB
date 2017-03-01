messagebus
=========

This is a role for reporting the status of a playbook onto the Unified Message
Bus for self service purposes.

*Note: This role is currently configured to trigger a jenkins job rather than
place a message on the UMB. This was done due to the lack of availability of
UMB at the time.*

Requirements
------------

This role requires the python proton module. Additionally, this role will not
function correctly without specifying a vault password. This password is
necessary to gain access to the certificate and key combination for
communications to the UMB. When the UMB is not used, the python-jenkins library is needed to send message to Jenkins.

Role Variables
--------------

All role variables are encrypted inside vars/main.yml. Only authorized users
should be able to alter these variables.

Dependencies
------------

There are no additional role dependencies.

User Data
---------
To capture data intended for the customer/user, use a standard debug task with
a message prefixed with "TICKET:". All ticket messages will be concatenated
with newlines when passed to the message bus.

Example Playbook
----------------

    - hosts: any
      tasks:
        - debug:
            msg: "TICKET: Sample data for the user"
      roles:
        - messagebus

Message Format
--------------

The role will send a message with the following format at the end of playbook
execution.

```
{
    "status": # SUCCESS or FAILURE
    "job_id": # Identifier/URL of the Ansible job
    "service_now_url": # ServiceNow table API URL for the ticket
    "user_data": # All debug messages prefixed with "TICKET:"
    "output": # Experimental, not used yet
}
```

License
-------

BSD

Author Information
------------------

Please contact either pnt-devops-ss@redhat.com or pnt-devops-auto@redhat.com
with any questions.
