Install Pipenv and dependencies:
bash
Copy
Edit
pip install pipenv
cd /path/to/migration-script
pipenv install paramiko python-dotenv
This creates a virtual environment and installs the required packages.
Configure variables:
Copy .env_example to .env and fill in the actual values (SSH hosts, users, key paths or passwords, database credentials, and which parts to run). For example, set DRY_RUN=true for a test run.
Run the script:
Use Pipenv to execute the script, ensuring the .env is loaded automatically:
bash
Copy
Edit
pipenv run python migrate.py
Or activate the shell and run:
bash
Copy
Edit
pipenv shell
python migrate.py
The script logs each step, and if any error occurs it will stop with a message. In dry-run mode, it will print the planned actions without executing them.
Verify the transfer:
After completion, check the target server’s public_html and mail directories for the copied files, and confirm that the target database has the expected tables. The script already performs basic file existence/size checks after each step.