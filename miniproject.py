import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, EmailStr

app = FastAPI(
    title="Team Task Management API",
    description="Hệ thống backend quản lý công việc nhóm hiệu năng cao chuẩn RESTful API."
)


class TaskCreateSchema(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str
    assignee: str = Field(min_length=2)
    priority: int = Field(ge=1, le=5)


class TaskUpdateSchema(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str
    assignee: str = Field(min_length=2)
    priority: int = Field(ge=1, le=5)
    status: str

class TaskPublicResponse(BaseModel):
    id: int
    title: str
    description: str
    assignee: str
    priority: int
    status: str
    created_at: str

class TaskSearchResponse(BaseModel):
    total: int
    results: List[TaskPublicResponse]


tasks_db: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "Setup FastAPI Framework",
        "description": "Initialize project structure and initial routing configuration.",
        "assignee": "Developer A",
        "priority": 5,
        "status": "done",
        "created_at": "2026-07-01T08:00:00Z",
        "internal_notes": "SYSTEM_LOG: Initial setup completed on staging server."
    },
    {
        "id": 2,
        "title": "Implement User Authentication",
        "description": "Build OAuth2 password bearer flow with JWT token verification.",
        "assignee": "Developer B",
        "priority": 4,
        "status": "in_progress",
        "created_at": "2026-07-02T09:30:00Z",
        "internal_notes": "CRITICAL_LOG: Secret keys rotated locally."
    }
]


@app.exception_handler(HTTPException)
def unified_http_exception_handler(request: Request, exc: HTTPException):
    # Trích xuất mã định danh lỗi nội bộ (Error Code) từ detail nếu được truyền dạng dict
    if isinstance(exc.detail, dict):
        error_code = exc.detail.get("error_code", "ERR-UNKNOWN")
        message = exc.detail.get("message", exc.detail)
        technical_error = exc.detail.get("error", "No additional developer logs available.")
    else:
        error_code = "ERR-GENERIC"
        message = str(exc.detail)
        technical_error = "An explicit HTTP exception was raised without technical payload details."

    envelope = {
        "statusCode": exc.status_code,
        "message": message,
        "data": None,
        "error": technical_error,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "path": request.url.path
    }
    return JSONResponse(status_code=exc.status_code, content=envelope)

@app.exception_handler(RequestValidationError)
def unified_validation_exception_handler(request: Request, exc: RequestValidationError):
    is_priority_error = False
    for error in exc.errors():
        if "priority" in error.get("loc", []):
            is_priority_error = True
            break

    if is_priority_error:
        status_code = 422
        message = "Lỗi: Mức độ ưu tiên công việc không hợp lệ (Phải từ 1 đến 5)!"
        technical_error = "Validation error: Priority field numerical bounds limits constraint violation. Value must be ge=1 and le=5."
    else:
        status_code = 422
        message = "Lỗi: Dữ liệu đầu vào sai định dạng hoặc thiếu trường bắt buộc!"
        technical_error = "Gateway validation error: Input json parameters datatype hints mismatch or core required fields missing."

    envelope = {
        "statusCode": status_code,
        "message": message,
        "data": None,
        "error": technical_error,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "path": request.url.path
    }
    return JSONResponse(status_code=status_code, content=envelope)


@app.get("/tasks/search", response_model=TaskSearchResponse)
def search_and_filter_tasks(keyword: Optional[str] = None, status: Optional[str] = None):
    results = []
    
    for task in tasks_db:
        match_keyword = True
        match_status = True
        
        if keyword is not None and keyword.strip() != "":
    
            pattern = re.compile(re.escape(keyword.strip()), re.IGNORECASE)
            
            in_title = bool(pattern.search(task["title"]))
            in_assignee = bool(pattern.search(task["assignee"]))
            
            if not in_title and not in_assignee:
                match_keyword = False
                
        if status is not None and status.strip() != "":
            if task["status"] != status.strip():
                match_status = False
                
        if match_keyword and match_status:
            results.append(task)
            
    return {
        "total": len(results),
        "results": results
    }


@app.post("/tasks", response_model=TaskPublicResponse, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreateSchema):
    
    is_duplicated = False
    for task in tasks_db:
        if task["title"] == payload.title:
            is_duplicated = True
            break
            
    if is_duplicated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Lỗi: Tiêu đề công việc này đã tồn tại trong nhóm!",
                "error": "Task conflict: Title field values duplicates an existing record in the temporary database storage."
            }
        )
        
    # Tự động gán ID tăng dần (id = max_current_id + 1)
    new_id = 1
    if tasks_db:
        max_id = tasks_db[0]["id"]
        for task in tasks_db:
            if task["id"] > max_id:
                max_id = task["id"]
        new_id = max_id + 1
        
    new_task = {
        "id": new_id,
        "title": payload.title,
        "description": payload.description,
        "assignee": payload.assignee,
        "priority": payload.priority,
        "status": "todo",  
        "created_at": datetime.utcnow().isoformat() + "Z",  # Tự động ghi nhận thời gian khởi tạo
        "internal_notes": "SYSTEM_LOG: Automatically generated record upon student request."
    }
    
    tasks_db.append(new_task)
    return new_task


@app.get("/tasks/{task_id}", response_model=TaskPublicResponse)
def get_task_detail(task_id: int):
    
    target_task = None
    for task in tasks_db:
        if task["id"] == task_id:
            target_task = task
            break
            
    if target_task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Lỗi: Không tìm thấy ID công việc yêu cầu trong hệ thống!",
                "error": "Resource missing error: Target task entity parameter [task_id] can not be located within current active database scope."
            }
        )
        
    return target_task


@app.put("/tasks/{task_id}", response_model=TaskPublicResponse)
def update_task(task_id: int, payload: TaskUpdateSchema):
   
    allowed_status = ["todo", "in_progress", "done"]
    is_valid_status = False
    for item in allowed_status:
        if item == payload.status:
            is_valid_status = True
            break
            
    if not is_valid_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Lỗi: Trạng thái công việc cập nhật không đúng quy định!",
                "error": "Business logic error: Invalid task status value. Allowed enumerated selection list: ['todo', 'in_progress', 'done']."
            }
        )

    target_index = -1
    for index in range(len(tasks_db)):
        if tasks_db[index]["id"] == task_id:
            target_index = index
            break
            
    if target_index == -1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Lỗi: Không tìm thấy ID công việc yêu cầu trong hệ thống!",
                "error": "Resource missing error: Target task entity parameter [task_id] can not be located within current active database scope."
            }
        )
        
    tasks_db[target_index]["title"] = payload.title
    tasks_db[target_index]["description"] = payload.description
    tasks_db[target_index]["assignee"] = payload.assignee
    tasks_db[target_index]["priority"] = payload.priority
    tasks_db[target_index]["status"] = payload.status
    
    return tasks_db[target_index]



@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int):
    
    target_index = -1
    for index in range(len(tasks_db)):
        if tasks_db[index]["id"] == task_id:
            target_index = index
            break
            
    
    if target_index == -1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Lỗi: Không tìm thấy ID công việc yêu cầu trong hệ thống!",
                "error": "Resource missing error: Target task entity parameter [task_id] can not be located within current active database scope."
            }
        )
        
    
    tasks_db.pop(target_index)
    
    
    return None