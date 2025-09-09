"""
Feature: Get available platform types
  As a frontend application
  I want to retrieve available platform types
  So that I can display platform options to users

Scenario: Successfully get platform types without authentication
  Given no authentication is required
  When a request is made to get platform types
  Then the system returns all available platform types
  And includes WHATSAPP, TELEGRAM, INSTAGRAM platforms
  And does not require authentication

Scenario: Platform types are returned as strings
  Given the platform types endpoint is called
  When the response is received
  Then all platform types are returned as string values
  And the response is a list format
"""

import pytest
from apis.channels import get_platform_types
from models.channels import PlatformType


@pytest.mark.asyncio
async def test_get_platform_types_success():
    # Given no authentication is required
    # When a request is made to get platform types
    result = await get_platform_types()
    
    # Then the system returns all available platform types
    assert isinstance(result, list)
    assert len(result) == len(PlatformType)
    
    # And includes WHATSAPP, TELEGRAM, INSTAGRAM platforms
    assert "WHATSAPP" in result
    assert "TELEGRAM" in result
    assert "INSTAGRAM" in result
    assert "WHATSAPP_TWILIO" in result


@pytest.mark.asyncio
async def test_platform_types_as_strings():
    # Given the platform types endpoint is called
    # When the response is received
    result = await get_platform_types()
    
    # Then all platform types are returned as string values
    for platform in result:
        assert isinstance(platform, str)
    
    # And the response is a list format
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_platform_types_match_enum_values():
    # Ensure the endpoint returns exactly the enum values
    result = await get_platform_types()
    expected_platforms = [platform.value for platform in PlatformType]
    
    # Sort both lists to ensure order doesn't matter
    assert sorted(result) == sorted(expected_platforms)


@pytest.mark.asyncio
async def test_platform_types_no_authentication_required():
    # This test verifies that the endpoint doesn't require any dependencies
    # The function should be callable directly without auth tokens or sessions
    result = await get_platform_types()
    
    # Should return successfully without any authentication
    assert result is not None
    assert len(result) > 0