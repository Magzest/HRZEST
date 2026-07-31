import React from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
} from "react-native";
import { DrawerContentScrollView } from "@react-navigation/drawer";
import { getFocusedRouteNameFromRoute } from "@react-navigation/native";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../store/AuthContext";

export default function AdminDrawerContent(props) {
  const { navigation, state } = props;
  const { signOut } = useAuth();

  const drawerRoute = state.routes[state.index];

  const activeRoute =
    getFocusedRouteNameFromRoute(drawerRoute) ?? drawerRoute.name;

  const handleLogout = () => {
    signOut();
  };

  // ─────────────────────────────────────────────────────────────
  //  ZERO DUPLICATION POLICY:
  //  Items present in the Bottom Tab Bar (Home, Staff, Attendance,
  //  Approvals, Settings) are EXCLUDED from the drawer so that
  //  no menu item repeats in both places.
  // ─────────────────────────────────────────────────────────────
  const menuItems = [
    // ANALYTICS & REPORTS
    {
      title: "Analytics & Reports",
      icon: "bar-chart-outline",
      iconFocused: "bar-chart",
      route: "Analytics",
      section: "ANALYTICS & REPORTS",
    },

    // HR OPERATIONS & MANAGEMENT
    {
      title: "Mark Attendance",
      icon: "create-outline",
      iconFocused: "create",
      route: "MarkAttendance",
      section: "HR OPERATIONS",
    },
    {
      title: "OT & Comp-Off",
      icon: "time-outline",
      iconFocused: "time",
      route: "CompOff",
      section: "HR OPERATIONS",
    },
    {
      title: "Resignation Requests",
      icon: "exit-outline",
      iconFocused: "exit",
      route: "Resignations",
      section: "HR OPERATIONS",
    },
    {
      title: "Performance & KPIs",
      icon: "trending-up-outline",
      iconFocused: "trending-up",
      route: "Performance",
      section: "HR OPERATIONS",
    },
    {
      title: "Onboarding Tasks",
      icon: "briefcase-outline",
      iconFocused: "briefcase",
      route: "Onboarding",
      section: "HR OPERATIONS",
    },
    {
      title: "Organization Chart",
      icon: "git-network-outline",
      iconFocused: "git-network",
      route: "OrgChart",
      section: "HR OPERATIONS",
    },

    // PAYROLL & COMPENSATION
    {
      title: "Salary & Payslips",
      icon: "wallet-outline",
      iconFocused: "wallet",
      route: "Payroll",
      section: "PAYROLL & COMP",
    },

    // SUPPORT & HELPDESK
    {
      title: "Support Tickets",
      icon: "ticket-outline",
      iconFocused: "ticket",
      route: "Tickets",
      section: "SUPPORT & HELPDESK",
    },
  ];

  const renderMenuItem = (item) => {
    const active = activeRoute === item.route;

    return (
      <TouchableOpacity
        key={item.title}
        activeOpacity={0.85}
        style={[styles.menuItem, active && styles.activeMenuItem]}
        onPress={() => {
          navigation.navigate("AdminTabs", {
            screen: item.route,
          });
          navigation.closeDrawer();
        }}
      >
        <Ionicons
          name={active ? item.iconFocused : item.icon}
          size={20}
          color={active ? "#FFFFFF" : "#173B8C"}
        />

        <Text style={[styles.menuText, active && styles.activeMenuText]}>
          {item.title}
        </Text>

        <Ionicons
          name="chevron-forward"
          size={16}
          color={active ? "#FFFFFF" : "#94A3B8"}
        />
      </TouchableOpacity>
    );
  };

  const renderSection = (title, section) => {
    const items = menuItems.filter((item) => item.section === section);
    if (items.length === 0) return null;

    return (
      <View style={styles.section} key={section}>
        <Text style={styles.sectionTitle}>{title}</Text>
        {items.map(renderMenuItem)}
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <DrawerContentScrollView
        {...props}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {/* Header */}
        <View style={styles.header}>
          <View style={styles.avatar}>
            <Ionicons name="shield-checkmark" size={38} color="#173B8C" />
            <View style={styles.onlineDot} />
          </View>

          <Text style={styles.name}>Administrator</Text>

          <View style={styles.roleBadge}>
            <Text style={styles.roleText}>Super Administrator</Text>
          </View>

          <Text style={styles.empId}>ADMIN001</Text>
        </View>

        <View style={styles.divider} />

        {renderSection("ANALYTICS & REPORTS", "ANALYTICS & REPORTS")}
        {renderSection("HR OPERATIONS", "HR OPERATIONS")}
        {renderSection("PAYROLL & COMP", "PAYROLL & COMP")}
        {renderSection("SUPPORT & HELPDESK", "SUPPORT & HELPDESK")}
      </DrawerContentScrollView>

      {/* Bottom Logout */}
      <View style={styles.bottomContainer}>
        <TouchableOpacity
          activeOpacity={0.85}
          style={styles.logoutButton}
          onPress={handleLogout}
        >
          <Ionicons name="log-out-outline" size={20} color="#EF4444" />
          <Text style={styles.logoutText}>Logout</Text>
        </TouchableOpacity>

        <Text style={styles.version}>Attendance SaaS v1.0.0</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F8FAFC",
  },
  scrollContent: {
    paddingBottom: 12,
  },
  header: {
    alignItems: "center",
    paddingTop: 12,
    paddingBottom: 16,
    paddingHorizontal: 20,
    backgroundColor: "#FFFFFF",
  },
  avatar: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "#EEF4FF",
    justifyContent: "center",
    alignItems: "center",
    position: "relative",
    shadowColor: "#000",
    shadowOpacity: 0.06,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 3,
  },
  onlineDot: {
    position: "absolute",
    bottom: 4,
    right: 4,
    width: 14,
    height: 14,
    borderRadius: 7,
    backgroundColor: "#22C55E",
    borderWidth: 2.5,
    borderColor: "#FFFFFF",
  },
  name: {
    marginTop: 12,
    fontSize: 18,
    fontWeight: "800",
    color: "#0F172A",
  },
  roleBadge: {
    marginTop: 8,
    backgroundColor: "#EEF4FF",
    paddingHorizontal: 14,
    paddingVertical: 4,
    borderRadius: 20,
  },
  roleText: {
    color: "#173B8C",
    fontWeight: "700",
    fontSize: 12,
  },
  empId: {
    marginTop: 6,
    color: "#94A3B8",
    fontSize: 12,
    fontWeight: "600",
  },
  divider: {
    height: 1,
    backgroundColor: "#E2E8F0",
    marginVertical: 10,
    marginHorizontal: 16,
  },
  section: {
    marginBottom: 8,
    paddingHorizontal: 14,
  },
  sectionTitle: {
    marginBottom: 6,
    marginLeft: 6,
    fontSize: 10,
    fontWeight: "800",
    color: "#94A3B8",
    letterSpacing: 1.1,
  },
  menuItem: {
    height: 44,
    borderRadius: 12,
    paddingHorizontal: 14,
    marginBottom: 4,
    backgroundColor: "#FFFFFF",
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#F1F5F9",
    elevation: 1,
  },
  activeMenuItem: {
    backgroundColor: "#173B8C",
    borderColor: "#173B8C",
    borderLeftWidth: 4,
    borderLeftColor: "#22C55E",
  },
  menuText: {
    flex: 1,
    marginLeft: 12,
    color: "#0F172A",
    fontWeight: "700",
    fontSize: 14,
  },
  activeMenuText: {
    color: "#FFFFFF",
  },
  bottomContainer: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 14,
    backgroundColor: "#F8FAFC",
  },
  logoutButton: {
    height: 46,
    borderRadius: 14,
    backgroundColor: "#FFF5F5",
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#FEE2E2",
  },
  logoutText: {
    marginLeft: 8,
    color: "#EF4444",
    fontWeight: "700",
    fontSize: 14,
  },
  version: {
    marginTop: 12,
    textAlign: "center",
    color: "#94A3B8",
    fontSize: 11,
  },
});
