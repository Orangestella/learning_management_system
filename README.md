# Learning Manage Flask Application

Learning Manage is a comprehensive educational management system built with Flask. It provides a platform for students, instructors, and administrators to manage courses, assignments, grades, and more.

## Features

- User authentication and role-based access control
- Course management with enrollment capabilities
- Assignment creation, submission, and grading
- Forum for course-related discussions
- Notification system for important updates

## Prerequisites

Before running the application, ensure you have the following prerequisites installed:

- Python 3.x
- Flask
- MySQL Connector

You will also need to set up a MySQL database and configure the connection in the `config.ini` file which should be created by yourself.

## Installation

1. Clone the repository:

   ```
   git clone https://github.com/yourusername/learnmanage.git
   ```

2. Navigate to the project directory:

   ```
   cd learnmanage
   ```

3. Create a virtual environment (optional but recommended):

   ```
   python3 -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

4. Install the dependencies:

   ```
   pip install -r requirements.txt
   ```

5. Configure the database connection in `config.ini`:

   ```
   [DATABASE]
   User = yourusername
   Password = yourpassword
   Host = localhost
   Database = learnmanage
   
   [SESSION]
   Secret_key = yoursecretkey
   ```

6. Initialize the database schema by running the SQL scripts (not included in this repository).

7. Run the application:

   ```
   python app.py
   ```

## Usage

- Access the application by navigating to `http://127.0.0.1:5000/` in your web browser.
- Login with your credentials or create a new account.
- Navigate through the available courses, assignments, forums, and other features.

## Frontend Notice

Please note that the frontend code in this repository is not mobile-responsive and has limited practical value. It is provided solely for demonstration purposes. If you intend to use this project, it is recommended to develop the frontend using a framework of your choice.

## Future Work

- Refactor and encapsulate the lengthy and redundant code in `app.py` to improve maintainability and scalability.

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Commit your changes.
4. Push to the branch and submit a pull request.


## Acknowledgments

- Flask for providing the web framework.
- MySQL for the database management system.
- Everyone who contributed to the open-source projects used in this application.

Please remember to update the `yourusername`, `yourpassword`, `yoursecretkey`, and the repository URL with the actual values you intend to use. The note about the front-end has been added as per your request, and the future work section now mentions the planned refactoring of the `app.py` code.
