"""
Project management endpoints.
"""

from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import update
from pydantic import BaseModel, field_serializer
from app.db.database import get_db
from app.db import models
from app.api.v1.auth import get_current_user
from app.services.credit_service import CreditService
from app.core.sanitization import sanitize_html, sanitize_text

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    description: str
    stage: str
    funding_need: str
    urgency: str
    founder_type: str | None = None
    timeline_constraints: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    stage: str | None = None
    funding_need: str | None = None
    urgency: str | None = None
    founder_type: str | None = None
    timeline_constraints: str | None = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str
    stage: str
    funding_need: str
    urgency: str
    founder_type: str | None
    timeline_constraints: str | None
    created_at: datetime
    updated_at: datetime | None
    
    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value: datetime | None, _info):
        """Serialize datetime to ISO format string."""
        return value.isoformat() if value else None
    
    class Config:
        from_attributes = True


def has_paid_assessment(user_id: int, db: Session) -> bool:
    """Check if user has at least one paid assessment."""
    paid_purchase = db.query(models.AssessmentPurchase).join(
        models.Evaluation, models.AssessmentPurchase.evaluation_id == models.Evaluation.id
    ).filter(
        models.Evaluation.user_id == user_id,
        models.AssessmentPurchase.purchase_type == "paid"
    ).first()
    return paid_purchase is not None


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new project.
    
    Project context is locked until user has made at least one paid assessment.
    This encourages users to try the free assessment first.
    """
    # Check if user has paid assessment (project context unlock)
    if not has_paid_assessment(current_user.id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project context is available after your first paid assessment. Use your free assessment first to see the value!"
        )
    
    # Sanitize user inputs to prevent XSS
    project_dict = project_data.model_dump()
    project_dict['name'] = sanitize_text(project_dict.get('name', ''))
    project_dict['description'] = sanitize_html(project_dict.get('description', '')) if project_dict.get('description') else ''
    project_dict['timeline_constraints'] = sanitize_html(project_dict.get('timeline_constraints', '')) if project_dict.get('timeline_constraints') else None
    
    db_project = models.Project(
        user_id=current_user.id,
        **project_dict
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all projects for the current user."""
    projects = db.query(models.Project).filter(
        models.Project.user_id == current_user.id
    ).all()
    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific project."""
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a project."""
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check if user has paid assessment (project context unlock)
    if not has_paid_assessment(current_user.id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project context is available after your first paid assessment."
        )
    
    update_data = project_data.model_dump(exclude_unset=True)
    # Sanitize user inputs
    if 'name' in update_data:
        update_data['name'] = sanitize_text(update_data['name'])
    if 'description' in update_data:
        update_data['description'] = sanitize_html(update_data['description']) if update_data['description'] else ''
    if 'timeline_constraints' in update_data:
        update_data['timeline_constraints'] = sanitize_html(update_data['timeline_constraints']) if update_data.get('timeline_constraints') else None
    
    for field, value in update_data.items():
        setattr(project, field, value)
    
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a project.
    
    If the project has evaluations linked to it, they will be automatically
    moved to the user's "Default Project" (created if it doesn't exist).
    This ensures no data loss while allowing project deletion.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        project = db.query(models.Project).filter(
            models.Project.id == project_id,
            models.Project.user_id == current_user.id
        ).first()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Check if project has evaluations
        linked_evaluations = db.query(models.Evaluation).filter(
            models.Evaluation.project_id == project_id
        ).all()
        evaluation_count = len(linked_evaluations)
        
        # If project has evaluations, unlink them by moving to default project
        # But skip if we're deleting the Default Project itself
        if evaluation_count > 0 and project.name != "Default Project":
            # Get or create default project for this user
            default_project = db.query(models.Project).filter(
                models.Project.user_id == current_user.id,
                models.Project.name == "Default Project"
            ).first()
            
            if not default_project:
                # Create default project if it doesn't exist
                # Use a savepoint to ensure we can rollback if needed
                savepoint = db.begin_nested()
                try:
                    default_project = models.Project(
                        user_id=current_user.id,
                        name="Default Project",
                        description="Not specified",
                        stage="Not specified",
                        funding_need="Not specified",
                        urgency="Not specified",
                        founder_type=None,
                        timeline_constraints=None
                    )
                    db.add(default_project)
                    db.flush()  # Flush to get the ID
                    
                    # Force the ID to be generated by accessing it
                    _ = default_project.id
                    
                    # Commit the savepoint to make the default project available
                    savepoint.commit()
                    
                    # Refresh to ensure we have the latest state
                    db.refresh(default_project)
                except Exception as e:
                    savepoint.rollback()
                    db.rollback()
                    logger.error(f"Failed to create default project: {str(e)}", exc_info=True)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to create default project for evaluation migration: {str(e)}"
                    )
            
            # Verify default_project has an ID before using it
            if not default_project or not default_project.id:
                db.rollback()
                logger.error(f"Default project has no ID - default_project: {default_project}, id: {default_project.id if default_project else 'None'}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve valid default project ID for evaluation migration"
                )
            
            # Store the ID to ensure we use a valid value
            default_project_id = default_project.id
            
            # Verify ID is not None
            if default_project_id is None:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Default project ID is None - cannot migrate evaluations"
                )
            
            # Unlink evaluations from deleted project and move to default project
            # Use direct SQL update to ensure it works
            try:
                stmt = update(models.Evaluation).where(
                    models.Evaluation.id.in_([e.id for e in linked_evaluations])
                ).values(project_id=default_project_id)
                db.execute(stmt)
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to update evaluations: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to migrate evaluations to default project: {str(e)}"
                )
            
            logger.info(f"Unlinked {evaluation_count} evaluation(s) from project {project_id} and moved to default project {default_project_id}")
        elif evaluation_count > 0 and project.name == "Default Project":
            # If deleting Default Project, we need to create a new one first
            # Get another project to move evaluations to, or create a new default
            other_project = db.query(models.Project).filter(
                models.Project.user_id == current_user.id,
                models.Project.id != project_id
            ).first()
            
            if other_project:
                # Move evaluations to another project using direct SQL update
                try:
                    stmt = update(models.Evaluation).where(
                        models.Evaluation.id.in_([e.id for e in linked_evaluations])
                    ).values(project_id=other_project.id)
                    db.execute(stmt)
                    logger.info(f"Unlinked {evaluation_count} evaluation(s) from Default Project {project_id} and moved to project {other_project.id}")
                except Exception as e:
                    db.rollback()
                    logger.error(f"Failed to update evaluations to other project: {str(e)}", exc_info=True)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to migrate evaluations to other project: {str(e)}"
                    )
            else:
                # No other projects exist - create a new default project first
                savepoint = db.begin_nested()
                try:
                    new_default_project = models.Project(
                        user_id=current_user.id,
                        name="Default Project",
                        description="Not specified",
                        stage="Not specified",
                        funding_need="Not specified",
                        urgency="Not specified",
                        founder_type=None,
                        timeline_constraints=None
                    )
                    db.add(new_default_project)
                    db.flush()
                    
                    # Force the ID to be generated by accessing it
                    _ = new_default_project.id
                    
                    # Commit the savepoint
                    savepoint.commit()
                    db.refresh(new_default_project)
                except Exception as e:
                    savepoint.rollback()
                    db.rollback()
                    logger.error(f"Failed to create replacement default project: {str(e)}", exc_info=True)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to create replacement default project: {str(e)}"
                    )
                
                if not new_default_project or not new_default_project.id:
                    db.rollback()
                    logger.error(f"New default project has no ID - new_default_project: {new_default_project}, id: {new_default_project.id if new_default_project else 'None'}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to retrieve valid replacement default project ID"
                    )
                
                # Store the ID to ensure we use a valid value
                new_default_project_id = new_default_project.id
                
                if new_default_project_id is None:
                    db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Replacement default project ID is None - cannot migrate evaluations"
                    )
                
                # Move evaluations to new default project using direct SQL update
                try:
                    stmt = update(models.Evaluation).where(
                        models.Evaluation.id.in_([e.id for e in linked_evaluations])
                    ).values(project_id=new_default_project_id)
                    db.execute(stmt)
                except Exception as e:
                    db.rollback()
                    logger.error(f"Failed to update evaluations to new default project: {str(e)}", exc_info=True)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to migrate evaluations to replacement default project: {str(e)}"
                    )
                
                logger.info(f"Unlinked {evaluation_count} evaluation(s) from Default Project {project_id} and moved to new Default Project {new_default_project_id}")
        
        # Delete the project
        db.delete(project)
        db.commit()
        
        # Return 204 No Content (FastAPI handles this automatically)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error deleting project {project_id} for user {current_user.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete project: {str(e)}"
        )

