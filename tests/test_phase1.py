#!/usr/bin/env python3
"""
Phase 1 Test Script
===================
Tests the enhanced database and alert manager components.

Run this to verify Phase 1 implementation is working correctly.
"""

import sys
import time
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from alert_manager import AlertManager
from enhanced_database import AlertLevel, AlertType, EnhancedDatabase, PersonState


def test_enhanced_database():
    """Test enhanced database functionality."""
    print("\n" + "=" * 60)
    print("Testing Enhanced Database")
    print("=" * 60)

    # Initialize database
    db = EnhancedDatabase("data/test_phase1.db")
    print("✅ Database initialized")

    # Test 1: Add person
    person_id = "test-person-001"
    db.add_person(person_id, state=PersonState.WAITING_TO_ENTER)
    print(f"✅ Added person: {person_id}")

    # Test 2: Record entry
    db.record_entry(person_id)
    assert person_id in db.inside_now
    print(f"✅ Recorded entry - currently inside: {len(db.inside_now)}")

    # Test 3: Add trajectory points
    for i in range(10):
        x = 100 + i * 10
        y = 200 + i * 5
        velocity = 1.5 + i * 0.1
        db.add_trajectory_point(person_id, x, y, "room_camera", velocity=velocity)

    trajectory = db.get_trajectory(person_id)
    assert len(trajectory) == 10
    print(f"✅ Added {len(trajectory)} trajectory points")

    # Test 4: Calculate average velocity
    avg_velocity = db.calculate_avg_velocity(person_id)
    print(f"✅ Average velocity: {avg_velocity:.2f} m/s")

    # Test 5: Create alert
    alert = db.create_alert(
        alert_type=AlertType.RUNNING,
        alert_level=AlertLevel.WARNING,
        person_id=person_id,
        camera_source="room_camera",
        message="Test running alert",
    )
    assert alert is not None
    print(f"✅ Created alert: {alert['alert_type']}")

    # Test 6: Record threat event
    db.record_threat_event(
        person_id=person_id,
        event_type="running",
        threat_score=0.75,
        velocity=4.5,
        trajectory_entropy=0.3,
        proximity_density=0.2,
        camera_source="room_camera",
    )
    print(f"✅ Recorded threat event")

    # Test 7: Get statistics
    stats = db.get_stats()
    print(f"\n📊 Database Statistics:")
    print(f"   - Currently Inside: {stats['currently_inside']}")
    print(f"   - Total Entries: {stats['total_entries']}")
    print(f"   - Total Alerts: {stats['total_alerts']}")
    print(f"   - Unique Visitors: {stats['unique_visitors']}")

    # Test 8: Record exit
    db.record_exit(person_id)
    assert person_id not in db.inside_now
    person = db.get_person(person_id)
    assert person["state"] == PersonState.EXITED.value
    assert person["permanent_uuid"] is not None
    print(f"✅ Recorded exit - permanent UUID: {person['permanent_uuid'][:8]}...")

    # Test 9: Unauthorized entry
    unauth_id = db.record_unauthorized_entry("temp-999", "room_camera")
    assert "UNAUTH" in unauth_id
    print(f"✅ Detected unauthorized entry: {unauth_id}")

    # Test 10: Person summary
    summary = db.get_person_summary(person_id)
    print(f"\n📋 Person Summary for {person_id}:")
    print(f"   - Trajectory Points: {summary['trajectory_points']}")
    print(f"   - Average Velocity: {summary['avg_velocity']:.2f} m/s")
    print(f"   - Alerts: {summary['alerts']}")
    print(f"   - Threat Events: {summary['threat_events']}")

    # Test 11: Export to JSON
    export_path = "data/test_export.json"
    db.export_to_json(export_path)
    assert Path(export_path).exists()
    print(f"✅ Exported to JSON: {export_path}")

    # Cleanup
    db.close()
    print("\n✅ All database tests passed!")

    return db


def test_alert_manager():
    """Test alert manager functionality."""
    print("\n" + "=" * 60)
    print("Testing Alert Manager")
    print("=" * 60)

    # Initialize alert manager
    manager = AlertManager(
        cooldown_seconds=2.0,
        console_output=True,
        file_logging=True,
        log_path="data/test_alerts.log",
        audio_alert=False,
    )
    print("✅ Alert manager initialized")

    # Test 1: Create INFO alert
    alert = manager.create_alert(
        AlertType.RUNNING,
        AlertLevel.INFO,
        "Person moving at normal speed",
        person_id="test-001",
        camera_source="room_camera",
    )
    assert alert is not None
    print("✅ Created INFO alert")

    time.sleep(0.5)

    # Test 2: Create WARNING alert
    alert = manager.create_alert(
        AlertType.RUNNING,
        AlertLevel.WARNING,
        "Person running detected",
        person_id="test-002",
        camera_source="room_camera",
        metadata={"velocity": 4.5},
    )
    assert alert is not None
    print("✅ Created WARNING alert")

    time.sleep(0.5)

    # Test 3: Create CRITICAL alert
    alert = manager.create_alert(
        AlertType.UNAUTHORIZED_ENTRY,
        AlertLevel.CRITICAL,
        "Unauthorized person detected",
        person_id="unauth-001",
        camera_source="room_camera",
    )
    assert alert is not None
    print("✅ Created CRITICAL alert")

    # Test 4: Test cooldown (should be suppressed)
    alert = manager.create_alert(
        AlertType.UNAUTHORIZED_ENTRY,
        AlertLevel.CRITICAL,
        "Another unauthorized alert (should be suppressed)",
        person_id="unauth-001",
        camera_source="room_camera",
    )
    assert alert is None
    print("✅ Cooldown working - alert suppressed")

    time.sleep(2.5)

    # Test 5: After cooldown (should go through)
    alert = manager.create_alert(
        AlertType.UNAUTHORIZED_ENTRY,
        AlertLevel.CRITICAL,
        "Alert after cooldown",
        person_id="unauth-001",
        camera_source="room_camera",
    )
    assert alert is not None
    print("✅ Alert created after cooldown")

    # Test 6: Mass gathering alert
    alert = manager.create_alert(
        AlertType.MASS_GATHERING,
        AlertLevel.WARNING,
        "Mass gathering in zone 1",
        camera_source="room_camera",
        metadata={"zone_id": "zone_1", "person_count": 8},
    )
    assert alert is not None
    print("✅ Created mass gathering alert")

    # Test 7: High threat score alert
    alert = manager.create_alert(
        AlertType.HIGH_THREAT_SCORE,
        AlertLevel.CRITICAL,
        "High threat score detected",
        person_id="test-003",
        camera_source="room_camera",
        metadata={"threat_score": 0.85},
    )
    assert alert is not None
    print("✅ Created high threat alert")

    # Test 8: Get statistics
    stats = manager.get_stats()
    print(f"\n📊 Alert Manager Statistics:")
    print(f"   - Total Alerts: {stats['total_alerts']}")
    print(f"   - Suppressed: {stats['suppressed_count']}")
    print(f"   - By Level: {stats['by_level']}")
    print(f"   - By Type: {stats['by_type']}")

    # Test 9: Get recent alerts
    recent = manager.get_recent_alerts(limit=5)
    print(f"\n📋 Recent Alerts ({len(recent)}):")
    for i, alert in enumerate(recent, 1):
        print(
            f"   {i}. [{alert['alert_level']}] {alert['alert_type']} - {alert['message']}"
        )

    # Test 10: Filter by level
    critical_alerts = manager.get_recent_alerts(level=AlertLevel.CRITICAL, limit=10)
    print(f"\n🚨 Critical Alerts: {len(critical_alerts)}")

    # Test 11: Get alerts for specific person
    person_alerts = manager.get_alerts_for_person("test-002")
    print(f"\n👤 Alerts for test-002: {len(person_alerts)}")

    # Test 12: Alert summary
    summary = manager.get_alert_summary(time_window_minutes=60)
    print(f"\n📈 Alert Summary (last 60 minutes):")
    print(f"   - Total: {summary['total_in_window']}")
    print(f"   - Critical: {summary['critical_count']}")
    print(f"   - Warning: {summary['warning_count']}")
    print(f"   - Info: {summary['info_count']}")

    # Test 13: Export alerts
    export_path = "data/test_alerts_export.json"
    manager.export_alerts(export_path)
    assert Path(export_path).exists()
    print(f"\n✅ Exported alerts to: {export_path}")

    print("\n✅ All alert manager tests passed!")

    return manager


def test_integration():
    """Test integration between database and alert manager."""
    print("\n" + "=" * 60)
    print("Testing Integration")
    print("=" * 60)

    db = EnhancedDatabase("data/test_integration.db")
    manager = AlertManager(
        cooldown_seconds=1.0,
        console_output=True,
        file_logging=False,
    )

    # Scenario: Person enters, runs, and triggers alert
    person_id = "integration-test-001"

    # Step 1: Entry
    db.add_person(person_id)
    db.record_entry(person_id)
    print(f"✅ Step 1: Person entered ({person_id})")

    # Step 2: Movement tracking
    for i in range(20):
        x = 100 + i * 15  # Moving quickly
        y = 200 + i * 10
        velocity = 3.0 + i * 0.2  # Accelerating
        db.add_trajectory_point(person_id, x, y, "room_camera", velocity=velocity)

    avg_vel = db.calculate_avg_velocity(person_id, window=5)
    print(f"✅ Step 2: Tracked movement (avg velocity: {avg_vel:.2f} m/s)")

    # Step 3: Detect running (velocity > 4.0 m/s)
    if avg_vel > 4.0:
        alert = manager.create_alert(
            AlertType.RUNNING,
            AlertLevel.WARNING,
            f"Person running (velocity: {avg_vel:.2f} m/s)",
            person_id=person_id,
            camera_source="room_camera",
        )

        # Also record in database
        db.create_alert(
            alert_type=AlertType.RUNNING,
            alert_level=AlertLevel.WARNING,
            person_id=person_id,
            camera_source="room_camera",
            message=f"Running detected: {avg_vel:.2f} m/s",
        )

        print(f"✅ Step 3: Running detected and alerted")

    # Step 4: Record threat event
    threat_score = min(avg_vel / 10.0, 1.0)
    db.record_threat_event(
        person_id=person_id,
        event_type="running",
        threat_score=threat_score,
        velocity=avg_vel,
        camera_source="room_camera",
    )
    print(f"✅ Step 4: Threat event recorded (score: {threat_score:.2f})")

    # Step 5: Exit
    db.record_exit(person_id)
    person = db.get_person(person_id)
    print(f"✅ Step 5: Person exited (duration: {person['duration_seconds']:.1f}s)")

    # Step 6: Verify data consistency
    summary = db.get_person_summary(person_id)
    stats = db.get_stats()
    alert_stats = manager.get_stats()

    print(f"\n📊 Integration Test Results:")
    print(f"   Database:")
    print(f"   - Trajectory points: {summary['trajectory_points']}")
    print(f"   - Alerts: {summary['alerts']}")
    print(f"   - Threat events: {summary['threat_events']}")
    print(f"   - Total exits: {stats['total_exits']}")
    print(f"\n   Alert Manager:")
    print(f"   - Total alerts: {alert_stats['total_alerts']}")

    db.close()
    print("\n✅ Integration test passed!")


def main():
    """Run all Phase 1 tests."""
    print("\n" + "=" * 60)
    print("PHASE 1 COMPONENT TESTS")
    print("Testing Enhanced Database & Alert Manager")
    print("=" * 60)

    try:
        # Test 1: Enhanced Database
        test_enhanced_database()

        # Test 2: Alert Manager
        test_alert_manager()

        # Test 3: Integration
        test_integration()

        # Final summary
        print("\n" + "=" * 60)
        print("🎉 ALL PHASE 1 TESTS PASSED!")
        print("=" * 60)
        print("\nPhase 1 components are ready:")
        print("✅ Enhanced Database with trajectory tracking")
        print("✅ Alert Manager with cooldown and logging")
        print("✅ Person state management")
        print("✅ Threat event recording")
        print("✅ Export to JSON")
        print("\nReady to proceed to Phase 2: Room Camera Implementation")
        print("=" * 60 + "\n")

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
