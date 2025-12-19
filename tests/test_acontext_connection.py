"""Test AContext connection.

This script tests the connection to the AContext server and verifies
that the basic operations work correctly.

Usage:
    python tests/test_acontext_connection.py
"""

import os
import sys

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_connection():
    """Test connection to AContext server."""
    print("Testing AContext connection...")

    try:
        from acontext import AcontextClient
    except ImportError:
        print("ERROR: acontext package not installed. Run: pip install acontext")
        return False

    api_key = os.getenv("ACONTEXT_API_KEY")
    base_url = os.getenv("ACONTEXT_BASE_URL", "http://localhost:8029/api/v1")

    if not api_key:
        print("ERROR: ACONTEXT_API_KEY environment variable not set")
        return False

    print(f"Base URL: {base_url}")
    print(f"API Key: {api_key[:10]}...")

    try:
        client = AcontextClient(
            api_key=api_key,
            base_url=base_url,
            timeout=30,
        )

        # Test ping
        result = client.ping()
        print(f"Ping result: {result}")

        if result == "pong":
            print("SUCCESS: Connection to AContext server established!")
            return True
        else:
            print(f"WARNING: Unexpected ping result: {result}")
            return False

    except Exception as e:
        print(f"ERROR: Failed to connect to AContext server: {e}")
        return False

    finally:
        try:
            client.close()
        except:
            pass


def test_manager_initialization():
    """Test AContextManager initialization."""
    print("\nTesting AContextManager initialization...")

    try:
        from minisweagent.acontext import AContextManager
    except ImportError as e:
        print(f"ERROR: Failed to import AContextManager: {e}")
        return False

    api_key = os.getenv("ACONTEXT_API_KEY")
    base_url = os.getenv("ACONTEXT_BASE_URL", "http://localhost:8029/api/v1")

    if not api_key:
        print("ERROR: ACONTEXT_API_KEY environment variable not set")
        return False

    config = {
        "enabled": True,
        "api_key": api_key,
        "base_url": base_url,
        "space": {
            "space_name": "test-mini-swe-agent",
        },
        "session": {
            "configs": {
                "test": True,
            }
        },
        "sop_search": {
            "enabled": True,
            "mode": "fast",
        }
    }

    manager = AContextManager(config)

    try:
        if manager.initialize():
            print(f"SUCCESS: AContextManager initialized!")
            print(f"  Space ID: {manager.space_id}")
            print(f"  Space Name: {manager.space_name}")
            print(f"  Session ID: {manager.session_id}")

            # Test message storage
            manager.store_message("user", "Test message from mini-swe-agent")
            print("  Message stored successfully")

            # Test SOP search
            sop_blocks = manager.search_sop("fix a bug in Python code")
            print(f"  SOP search returned {len(sop_blocks)} results")

            # Get task status
            status = manager.get_task_status()
            print(f"  Task status: {status}")

            return True
        else:
            print("ERROR: AContextManager initialization failed")
            return False

    except Exception as e:
        print(f"ERROR: {e}")
        return False

    finally:
        manager.close()


def test_disabled_mode():
    """Test AContextManager in disabled mode."""
    print("\nTesting AContextManager in disabled mode...")

    try:
        from minisweagent.acontext import AContextManager
    except ImportError as e:
        print(f"ERROR: Failed to import AContextManager: {e}")
        return False

    # Test with None config
    manager = AContextManager(None)
    assert not manager.enabled
    assert not manager.initialize()
    print("  Disabled mode (None config): OK")

    # Test with disabled config
    manager = AContextManager({"enabled": False})
    assert not manager.enabled
    assert not manager.initialize()
    print("  Disabled mode (enabled=False): OK")

    # Test with empty config
    manager = AContextManager({})
    assert not manager.enabled
    assert not manager.initialize()
    print("  Disabled mode (empty config): OK")

    print("SUCCESS: Disabled mode tests passed!")
    return True


if __name__ == "__main__":
    results = []

    # Test disabled mode (doesn't require server)
    results.append(("Disabled mode", test_disabled_mode()))

    # Test connection (requires server)
    results.append(("Connection", test_connection()))

    # Test manager initialization (requires server)
    results.append(("Manager initialization", test_manager_initialization()))

    print("\n" + "=" * 50)
    print("Test Results:")
    print("=" * 50)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")

    if all(passed for _, passed in results):
        print("\nAll tests passed!")
        sys.exit(0)
    else:
        print("\nSome tests failed!")
        sys.exit(1)
