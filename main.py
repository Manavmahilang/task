from fastapi import HTTPException
from pydantic import BaseModel
from fastapi import Depends
import mysql.connector
from fastapi import FastAPI
import jwt
import time
import json
import base64

app = FastAPI()

# Database connection
db = mysql.connector.connect(user='root', password='Manav@789mysql',
                               database='todo')
cursor = db.cursor()

# Request/response models
class ToDoItem(BaseModel):
    id: int
    description: str
    completed: bool

class ToDoItemCreate(BaseModel):
    description: str

class ToDoItemUpdate(BaseModel):
    description: str
    completed: bool

class User(BaseModel):
    id: int
    username: str
    token: str


# This should be a secret that only your server knows
SECRET_KEY = "my-secret-key"

def valid_token(auth_header):
  """
  Validates the token in the Authorization header of the request
  """
  # Extract the token from the header
  try:
      auth_type, token = auth_header.split()
      if auth_type.lower() != "bearer":
          raise ValueError("Invalid authorization type")
  except ValueError:
      return False

  # Decode the token and verify its signature
  try:
      decoded_token = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
  except (jwt.DecodeError, jwt.ExpiredSignatureError):
      return False

  # Check if the token has expired
  if "exp" in decoded_token and decoded_token["exp"] < time.time():
      return False

  # If the token is valid and has not expired, return the user id from the token
  return decoded_token["user_id"]


def json_response(data, status=200):
  """
  Creates a JSON response with the given data and HTTP status code
  """
  return (json.dumps(data), status, {"Content-Type": "application/json"})

def requires_auth(func):
  """
  A decorator that checks for a valid JWT token in the request header
  """
  def wrapper(request):
      auth_header = request.headers.get("Authorization")
      if not auth_header:
          return json_response({"error": "Authorization header is missing"}, status=401)
      user_id = valid_token(auth_header)
      if not user_id:
          return json_response({"error": "Invalid token"}, status=401)
      request.user_id = user_id
      return func(request)
  return wrapper

def get_todos_for_user(user_id):
  """
  Retrieves a list of todos for the given user
  """
  todos = []
  # Query the database for todos belonging to the user
  rows = db.execute("SELECT * FROM todos WHERE user_id = ?", (user_id,))
  for row in rows:
      todos.append({
          "id": row["id"],
          "title": row["title"],
          "completed": row["completed"]
      })
  return todos


# Use the decorator to protect the route
@app.route("/todos", methods=["GET"])
@requires_auth
def list_todos(request):
  # The request is authenticated, so we can access the user's todo list
  todos = get_todos_for_user(request.user_id)
  return json_response({"todos": todos})

def authenticate(token: str):
    # Check token against a list of valid tokens or a database of authorized users
    if token in valid_token:
        return get_user_by_token(token)
    else:
        return None

def get_user_by_token(token: str):
    # Query database for user associated with the given token
    query = "SELECT * FROM users WHERE token = %s"
    values = (token,)
    cursor.execute(query, values)
    result = cursor.fetchone()
    if result:
        # Return user object
        return User(id=result[0], username=result[1], token=result[2])
    else:
        # Return None if no user is found
        return None

# Authentication
def get_current_user(token: str = Depends(authenticate)):
    if not token:
        raise HTTPException(status_code=401, detail="Access denied")
    return get_user_by_token(token)

@app.post("/items/")
def create_item(item: ToDoItemCreate, user: str = Depends(get_current_user)):
    # Insert new item into database
    query = "INSERT INTO todo (description, completed) VALUES (%s, %s)"
    values = (item.description, False)
    cursor.execute(query, values)
    db.commit()
    id = cursor.lastrowid
    # Return ID of created item
    return {"id": id}

@app.put("/items/{id}")
def update_item(id: int, item: ToDoItemUpdate, user: str = Depends(get_current_user)):
    # Update item in database
    query = "UPDATE todo SET description = %s, completed = %s WHERE id = %s"
    values = (item.description, item.completed, id)
    cursor.execute(query, values)
    db.commit()
    return {"id": id}

@app.delete("/items/{id}")
def delete_item(id: int, user: str = Depends(get_current_user)):
    # Delete item from database
    query = "DELETE FROM todo WHERE id = %s"
    values = (id,)
    cursor.execute(query, values)
    db.commit()
    return {"id": id}

@app.get("/items/")
def read_items(skip: int = 0, limit: int = 100, user: str = Depends(get_current_user)):
    # Retrieve a list of items from the database
    query = "SELECT * FROM todo LIMIT %s OFFSET %s"
    values = (limit, skip)
    cursor.execute(query, values)
    results = cursor.fetchall()
    # Create a list of ToDoItem objects from the query results
    items = []
    for result in results:
        item = ToDoItem(id=result[0], description=result[1], completed=result[2])
        items.append(item)
    return items    