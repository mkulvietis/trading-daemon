import threading
import time
import pytest
from unittest.mock import MagicMock, patch
from src.state import InferenceStatus, app_state
from src.web_server import app, set_gemini_client

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_inference_status_initial(client):
    """Test initial inference status is NONE."""
    response = client.get('/api/inference')
    data = response.get_json()
    assert data['status'] == InferenceStatus.NONE.value

def test_trigger_inference_success(client):
    """Test triggering inference successfully."""
    mock_gemini = MagicMock()
    mock_gemini.run_inference.return_value = "Success Result"
    set_gemini_client(mock_gemini)
    
    # Reset state
    app_state.inference.status = InferenceStatus.NONE
    
    response = client.post('/api/inference')
    assert response.status_code == 202
    assert response.get_json()['status'] == 'running'
    
    # Wait for thread to complete
    time.sleep(0.5)
    
    status_response = client.get('/api/inference')
    data = status_response.get_json()
    assert data['status'] == InferenceStatus.COMPLETE.value
    assert data['result'] == "Success Result"

def test_trigger_inference_already_running(client):
    """Test triggering inference while already running returns 409."""
    # Force running state
    app_state.start_inference()
    
    response = client.post('/api/inference')
    assert response.status_code == 409
    
    # Reset state
    app_state.inference.status = InferenceStatus.NONE

def test_trigger_inference_failure(client):
    """Test inference failure handling."""
    mock_gemini = MagicMock()
    mock_gemini.run_inference.return_value = "Error: Something went wrong"
    set_gemini_client(mock_gemini)
    
    response = client.post('/api/inference')
    assert response.status_code == 202
    
    time.sleep(0.5)
    
    status_response = client.get('/api/inference')
    data = status_response.get_json()
    assert data['status'] == InferenceStatus.ERROR.value
    assert data['error'] == "Error: Something went wrong"

def test_auto_inference_endpoints(client):
    """Test getting and setting auto-inference interval."""
    # Set
    response = client.post('/api/auto-inference', json={'interval': 60})
    assert response.status_code == 200
    assert response.get_json()['interval'] == 60
    assert app_state.get_auto_inference_interval() == 60
    
    # Get
    response = client.get('/api/auto-inference')
    assert response.status_code == 200
    assert response.get_json()['interval'] == 60
    
    # Disable
    response = client.post('/api/auto-inference', json={'interval': 0})
    assert response.get_json()['interval'] == 0
