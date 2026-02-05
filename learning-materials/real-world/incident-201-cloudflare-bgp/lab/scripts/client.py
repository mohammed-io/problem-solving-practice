#!/usr/bin/env python3
"""
BGP Route Leak Lab

Demonstrates BGP route leaks and prefix hijacking.
"""

import subprocess
import time
import re


class BGPLab:
    def __init__(self):
        self.backbone = "bgp-backbone"
        self.cloudflare = "bgp-cloudflare"
        self.small_isp = "bgp-small-isp"
        self.malicious_isp = "bgp-malicious-isp"

    def run_vtysh(self, container, command):
        """Run vtysh command on a container."""
        full_cmd = f"docker-compose exec -T {container} vtysh -c '{command}'"
        result = subprocess.run(
            full_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout + result.stderr

    def get_bgp_routes(self, container):
        """Get BGP routes from container."""
        return self.run_vtysh(container, "show ip bgp")

    def get_bgp_summary(self, container):
        """Get BGP summary from container."""
        return self.run_vtysh(container, "show ip bgp summary")


# ============================================
# EXPERIMENT 1: Normal BGP Operation
# ============================================
def experiment_normal_operation(lab):
    """Show normal BGP route announcement."""
    print("\n" + "="*50)
    print("EXPERIMENT 1: Normal BGP Operation")
    print("="*50)

    print("\nScenario: Cloudflare announces its legitimate prefixes")
    print("  Expected: Backbone receives routes only from Cloudflare")

    print("\n[Backbone] BGP Summary:")
    print(lab.get_bgp_summary(lab.backbone))

    print("\n[Backbone] BGP Routes:")
    routes = lab.get_bgp_routes(lab.backbone)
    print(routes)

    # Parse routes to show origin
    if "173.245.48.0" in routes:
        print("\n  ✓ Cloudflare's prefix (173.245.48.0/24) is visible")
        print("  ✓ Traffic flows correctly to Cloudflare")


# ============================================
# EXPERIMENT 2: Route Leak Detection
# ============================================
def experiment_route_leak(lab):
    """Detect route leak from malicious ISP."""
    print("\n" + "="*50)
    print("EXPERIMENT 2: Route Leak Detection")
    print("="*50)

    print("\nScenario: Malicious ISP announces Cloudflare's prefix")
    print("  Expected: Backbone sees TWO paths to same prefix")

    print("\n[Backbone] Checking for duplicate route announcements...")

    routes = lab.get_bgp_routes(lab.backbone)

    # Look for Cloudflare's prefix in routes
    lines = routes.split('\n')
    cloudflare_prefixes = []
    for line in lines:
        if "173.245.48" in line:
            cloudflare_prefixes.append(line)

    print(f"\n  Found {len(cloudflare_prefixes)} route announcements for 173.245.48.0/24:")
    for prefix in cloudflare_prefixes:
        print(f"    {prefix}")

    if len(cloudflare_prefixes) > 1:
        print("\n  ⚠️  ROUTE LEAK DETECTED!")
        print("  Multiple AS paths to same prefix indicate hijack/leak")
    else:
        print("\n  ✓ No route leak detected")


# ============================================
# EXPERIMENT 3: AS Path Analysis
# ============================================
def experiment_as_path_analysis(lab):
    """Analyze AS paths to detect anomalies."""
    print("\n" + "="*50)
    print("EXPERIMENT 3: AS Path Analysis")
    print("="*50)

    print("\nChecking AS path validity...")

    print("\n[Backbone] Detailed route information:")
    output = lab.run_vtysh(lab.backbone, "show ip bgp 173.245.48.0/24")
    print(output)

    print("\nKey indicators of route leak:")
    print("  1. AS path contains unexpected transit AS")
    print("  2. Prefix appears from multiple neighbors")
    print("  3. First AS in path differs from origin AS")


# ============================================
# EXPERIMENT 4: Prefix Length Comparison
# ============================================
def experiment_prefix_length(lab):
    """Compare prefix lengths (more specific wins)."""
    print("\n" + "="*50)
    print("EXPERIMENT 4: Prefix Length Comparison")
    print("="*50)

    print("\nScenario: More specific prefixes are preferred")
    print("  Rule: /25 beats /24 regardless of AS path length")

    print("\n[Backbone] All routes with prefix lengths:")
    routes = lab.get_bgp_routes(lab.backbone)

    for line in routes.split('\n'):
        if '>' in line and '173.245' in line:
            print(f"  {line}")

    print("\n  💡 In real incident: Virginia ISP announced /24")
    print("     beating Cloudflare's /16 announcement")


# ============================================
# EXPERIMENT 5: RPKI Validation (Simulated)
# ============================================
def experiment_rpki_validation(lab):
    """Simulate RPKI validation."""
    print("\n" + "="*50)
    print("EXPERIMENT 5: RPKI Validation (Simulated)")
    print("="*50)

    print("\nRPKI (Resource Public Key Infrastructure) validates")
    print("that an AS is authorized to announce a prefix.")

    print("\nSimulating RPKI checks...")
    print("\n  Prefix: 173.245.48.0/24")
    print("  Legitimate Owner: AS 13335 (Cloudflare)")
    print("  Announced by: AS 13335 ✓ VALID")

    print("\n  Prefix: 173.245.48.0/24")
    print("  Announced by: AS 65002 (Malicious ISP)")
    print("  Result: ✗ INVALID (not authorized)")

    print("\n  💡 With RPKI, route leaks are automatically rejected!")


# ============================================
# EXPERIMENT 6: Mitigation Strategies
# ============================================
def experiment_mitigation(lab):
    """Show mitigation strategies."""
    print("\n" + "="*50)
    print("EXPERIMENT 6: Mitigation Strategies")
    print("="*50)

    print("\n1. Prefix Filtering (Route Filters)")
    print("   - Only accept prefixes registered to peer")
    print("   - Use IRR (Internet Routing Registry) databases")

    print("\n2. RPKI Validation")
    print("   - Deploy Route Origin Authorizations (ROAs)")
    print("   - Reject invalid routes automatically")

    print("\n3. Maximum Prefix Limits")
    print("   - Set max number of prefixes per peer")
    print("   - Session resets if limit exceeded")

    print("\n4. AS-Path Filtering")
    print("   - Reject routes with prepended AS paths")
    print("   - Filter based on expected AS path length")

    print("\n5. BGP Communities")
    print("   - Use communities to signal route preference")
    print("   - Tag routes with 'no-export' where appropriate")


# ============================================
# INTERACTIVE MENU
# ============================================
def print_menu():
    """Print interactive menu."""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║             🌐 BGP Route Leak Lab - Interactive                 ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    print("📋 Available Experiments:")
    print("  1. Normal BGP Operation")
    print("  2. Route Leak Detection")
    print("  3. AS Path Analysis")
    print("  4. Prefix Length Comparison")
    print("  5. RPKI Validation (Simulated)")
    print("  6. Mitigation Strategies")
    print("  7. Run All Experiments")
    print("  8. Exit")


def main():
    print_menu()

    lab = BGPLab()

    # Wait for BGP to converge
    print("\n⏳ Waiting for BGP sessions to establish...")
    time.sleep(5)

    while True:
        print_menu()
        choice = input("\nSelect experiment (1-8): ").strip()

        if choice == "1":
            experiment_normal_operation(lab)
        elif choice == "2":
            experiment_route_leak(lab)
        elif choice == "3":
            experiment_as_path_analysis(lab)
        elif choice == "4":
            experiment_prefix_length(lab)
        elif choice == "5":
            experiment_rpki_validation(lab)
        elif choice == "6":
            experiment_mitigation(lab)
        elif choice == "7":
            experiment_normal_operation(lab)
            experiment_route_leak(lab)
            experiment_as_path_analysis(lab)
            experiment_prefix_length(lab)
            experiment_rpki_validation(lab)
            experiment_mitigation(lab)
        elif choice == "8":
            print("\n👋 Thanks for learning about BGP route leaks!")
            break
        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()
