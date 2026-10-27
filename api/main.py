
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()

tasks = {}


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""


class TaskResponse(BaseModel):
    task_id: str
    title: str
    description: str
    status: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str


class TaskResultResponse(BaseModel):
    task_id: str
    status: str
    result: object | None = None
    message: str


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/tasks", status_code=201, response_model=TaskResponse)
def create_task(task: TaskCreate):
    task_id = str(uuid4())

    new_task = {
        "task_id": task_id,
        "title": task.title,
        "description": task.description,
        "status": "pending",
    }

    tasks[task_id] = new_task
    return new_task


@app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str):
    task = tasks.get(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task_id,
        "status": task["status"],
    }


@app.get("/tasks/{task_id}/result", response_model=TaskResultResponse)
def get_task_result(task_id: str):
    task = tasks.get(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task_id,
        "status": task["status"],
        "result": None,
        "message": "Task has not completed yet",
    }
