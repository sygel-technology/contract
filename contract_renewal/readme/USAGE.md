To auto-renew contract lines, you need to:
1.  Go to a contract line related to a contract with the "Recurrence at line level?" option active
2.  Activate the "Auto Renew" option.
3.	Select the extension length when the contract is auto renewed in the "Renew Every" field.

This module adds a new contract line state: "To-Renew". A cron finds the contract line in "To-Renew" state and the "Auto Renew" option active and sets a new "End Date" based on the values set in the "Renew Every" field.

There is an extra option in the contract line: "Manual Renew Needed?". Activate this options in those lines that might have to be renewed but the renewall does not have to be automatic. Instead, there is a button in the contract lines called "Renew", which is only visible for users in group "Technical Features". When this button is clicked, the contract line's end date is extended based on the values set in the "Renew Every" field.
