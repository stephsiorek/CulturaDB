"""
Pipeline API endpoints for triggering movie data fetches
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional, Dict, Any
from pydantic import BaseModel
import subprocess
import os
from pathlib import Path

router = APIRouter()

# Track running pipeline processes
_pipeline_status: Dict[str, Any] = {}


class PipelineRunRequest(BaseModel):
    """Request model for pipeline run"""
    endpoint: Optional[str] = "movie/popular"
    pages: int = 1
    page_start: int = 1
    page_end: Optional[int] = None
    primary_release_date_gte: Optional[str] = None
    primary_release_date_lte: Optional[str] = None
    since_days: Optional[int] = None
    use_discover: bool = False
    params: Optional[str] = None


class PipelineStatusResponse(BaseModel):
    """Pipeline status response"""
    status: str  # "running", "completed", "failed", "not_found"
    message: Optional[str] = None


def run_pipeline_task(request: PipelineRunRequest):
    """Background task to run the pipeline"""
    try:
        # Build command - go up from backend/api/routes/pipeline.py to project root
        # Path: backend/api/routes/pipeline.py -> backend/api/routes -> backend/api -> backend -> root
        script_path = Path(__file__).parent.parent.parent.parent / "movies.py"
        print(f"Pipeline script path: {script_path}")
        print(f"Script exists: {script_path.exists()}")
        
        if not script_path.exists():
            raise FileNotFoundError(f"Pipeline script not found at {script_path}")
        
        cmd = ["python", str(script_path)]
        
        if request.endpoint:
            cmd.extend(["--endpoint", request.endpoint])
        if request.pages:
            cmd.extend(["--pages", str(request.pages)])
        if request.page_start:
            cmd.extend(["--page-start", str(request.page_start)])
        if request.page_end:
            cmd.extend(["--page-end", str(request.page_end)])
        if request.primary_release_date_gte:
            cmd.extend(["--primary-release-date-gte", request.primary_release_date_gte])
        if request.primary_release_date_lte:
            cmd.extend(["--primary-release-date-lte", request.primary_release_date_lte])
        if request.since_days:
            cmd.extend(["--since-days", str(request.since_days)])
        if request.use_discover:
            cmd.append("--use-discover")
        if request.params:
            cmd.extend(["--params", request.params])
        
        # Run pipeline
        print(f"Running command: {' '.join(cmd)}")
        print(f"Working directory: {script_path.parent}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=script_path.parent,
            env=os.environ.copy()  # Pass environment variables (including .env)
        )
        
        print(f"Pipeline return code: {result.returncode}")
        print(f"Pipeline stdout: {result.stdout[:500] if result.stdout else 'None'}")
        print(f"Pipeline stderr: {result.stderr[:500] if result.stderr else 'None'}")
        
        if result.returncode == 0:
            _pipeline_status["last_run"] = {
                "status": "completed",
                "message": result.stdout or "Pipeline completed successfully",
                "stderr": result.stderr
            }
        else:
            _pipeline_status["last_run"] = {
                "status": "failed",
                "message": result.stderr or result.stdout or "Pipeline failed",
                "error": result.stderr
            }
    except Exception as e:
        _pipeline_status["last_run"] = {
            "status": "failed",
            "message": f"Error running pipeline: {str(e)}"
        }


@router.post("/run")
async def run_pipeline(
    request: PipelineRunRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger a pipeline run in the background
    """
    try:
        # Add background task
        background_tasks.add_task(run_pipeline_task, request)
        
        _pipeline_status["last_run"] = {
            "status": "running",
            "message": "Pipeline started"
        }
        
        return {
            "status": "started",
            "message": "Pipeline run started in background"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting pipeline: {str(e)}")


@router.get("/status", response_model=PipelineStatusResponse)
async def get_pipeline_status():
    """
    Get the status of the last pipeline run
    """
    if "last_run" not in _pipeline_status:
        return PipelineStatusResponse(
            status="not_found",
            message="No pipeline runs found"
        )
    
    last_run = _pipeline_status["last_run"]
    return PipelineStatusResponse(
        status=last_run.get("status", "unknown"),
        message=last_run.get("message")
    )

