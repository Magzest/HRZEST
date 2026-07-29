<<<<<<< HEAD
import React from "react";
import {
  View,
 Text,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
  ScrollView,
} from "react-native";

import { DrawerContentScrollView } from "@react-navigation/drawer";
import { getFocusedRouteNameFromRoute } from "@react-navigation/native";
import { Ionicons } from "@expo/vector-icons";

import { useAuth } from "../../store/AuthContext";
import THEME from "../../constants/theme";

export default function AdminDrawerContent(props) {
  const { navigation, state } = props;
  const { signOut } = useAuth();

  const drawerRoute = state.routes[state.index];

  const activeRoute =
    getFocusedRouteNameFromRoute(drawerRoute) ??
    drawerRoute.name;

  const handleLogout = () => {
    signOut();
  };

 const menuItems = [

  // HR MANAGEMENT

  {
    title: "Mark Attendance",
    icon: "create-outline",
    route: "MarkAttendance",
    section: "HR",
  },

  {
    title: "Salary & Payslips",
    icon: "wallet-outline",
    route: "Payroll",
    section: "HR",
  },

  {
    title: "Leaves & Holidays",
    icon: "calendar-clear-outline",
    route: "LeaveRequests",
    section: "HR",
  },

  {
    title: "OT & Comp-off",
    icon: "time-outline",
    route: "CompOff",
    section: "HR",
  },

  // EMPLOYEE

  {
    title: "Performance",
    icon: "trending-up-outline",
    route: "Performance",
    section: "EMPLOYEE",
  },

  {
    title: "Onboarding",
    icon: "briefcase-outline",
    route: "Onboarding",
    section: "EMPLOYEE",
  },

  {
    title: "Organization Chart",
    icon: "git-network-outline",
    route: "Organization",
    section: "EMPLOYEE",
  },

  // ADMIN

  
  

  

  

 

  {
    title: "Admin Tools",
    icon: "construct-outline",
    route: "AdminTools",
    section: "ADMIN",
  },

];

  const renderMenuItem = (item) => {
    const active = activeRoute === item.route;

    return (
      <TouchableOpacity
        key={item.title}
        activeOpacity={0.85}
        style={[
          styles.menuItem,
          active && styles.activeMenuItem,
        ]}
        onPress={() => {
          navigation.navigate("AdminTabs", {
            screen: item.route,
          });

          navigation.closeDrawer();
        }}
      >
        <Ionicons
          name={item.icon}
          size={22}
          color={
            active
              ? "#FFFFFF"
              : "#173B8C"
          }
        />

        <Text
          style={[
            styles.menuText,
            active &&
              styles.activeMenuText,
          ]}
        >
          {item.title}
        </Text>

        <Ionicons
          name="chevron-forward"
          size={18}
          color={
            active
              ? "#FFFFFF"
              : "#94A3B8"
          }
        />
      </TouchableOpacity>
    );
  };

  const renderSection = (
    title,
    section
  ) => (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>
        {title}
      </Text>

      {menuItems
        .filter(
          (item) =>
            item.section === section
        )
        .map(renderMenuItem)}
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <DrawerContentScrollView
        {...props}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={
          styles.scrollContent
        }
      >
        {/* Header */}

        <View style={styles.header}>
          <View style={styles.avatar}>

            <Ionicons
              name="shield-checkmark"
              size={42}
              color="#173B8C"
            />

            <View style={styles.onlineDot} />

          </View>

          <Text style={styles.name}>
            Administrator
          </Text>

          <View style={styles.roleBadge}>
            <Text style={styles.roleText}>
              Super Administrator
            </Text>
          </View>

          <Text style={styles.empId}>
            ADMIN001
          </Text>

        </View>

        <View style={styles.divider} />

        {renderSection("HR MANAGEMENT", "HR")}

{renderSection("EMPLOYEE", "EMPLOYEE")}

{renderSection("ADMINISTRATION", "ADMIN")}
              </DrawerContentScrollView>

      {/* Bottom */}

      <View style={styles.bottomContainer}>

        <TouchableOpacity
          activeOpacity={0.85}
          style={styles.logoutButton}
          onPress={handleLogout}
        >
          <Ionicons
            name="log-out-outline"
            size={22}
            color="#EF4444"
          />

          <Text style={styles.logoutText}>
            Logout
          </Text>

        </TouchableOpacity>

        <Text style={styles.version}>
          Version 1.0.0
        </Text>

      </View>

    </SafeAreaView>
  );
}

const styles = StyleSheet.create({

  container: {
    flex: 1,
    backgroundColor: "#F7F9FC",
  },

  scrollContent: {
    paddingBottom: 12,
  },

  header: {
    alignItems: "center",
    paddingTop: 8,
    paddingBottom: 12,
    paddingHorizontal: 24,
    backgroundColor: "#FFFFFF",
  },

  avatar: {
    width: 72,
    height: 72,
    borderRadius: 36,

    backgroundColor: "#EEF4FF",

    justifyContent: "center",
    alignItems: "center",

    position: "relative",

    shadowColor: "#000",
    shadowOpacity: 0.08,
    shadowRadius: 10,
    shadowOffset: {
      width: 0,
      height: 5,
    },

    elevation: 4,
  },

  onlineDot: {
    position: "absolute",

    bottom: 8,
    right: 8,

    width: 16,
    height: 16,

    borderRadius: 8,

    backgroundColor: "#22C55E",

    borderWidth: 3,
    borderColor: "#FFFFFF",
  },

  name: {
    marginTop: 16,

    fontSize: 21,

    fontWeight: "800",

    color: "#0F172A",
  },

  roleBadge: {
    marginTop: 12,

    backgroundColor: "#EEF4FF",

    paddingHorizontal: 16,
    paddingVertical: 5,

    borderRadius: 30,
  },

  roleText: {
    color: "#173B8C",

    fontWeight: "700",

    fontSize: 13,
  },

  empId: {
    marginTop: 10,

    color: "#94A3B8",

    fontSize: 13,

    fontWeight: "600",
  },

  divider: {
    height: 1,

    backgroundColor: "#EEF2F7",

    marginVertical: 12,

    marginHorizontal: 20,
  },

  section: {
    marginBottom: 10,

    paddingHorizontal: 16,
  },

  sectionTitle: {
    marginBottom: 6,

    marginLeft: 8,

    fontSize: 11,

    fontWeight: "700",

    color: "#94A3B8",

    letterSpacing: 1.2,
  },

  menuItem: {
    height: 48,

    borderRadius: 14,

    paddingHorizontal: 16,

    marginBottom: 6,

    backgroundColor: "#FFFFFF",

    flexDirection: "row",

    alignItems: "center",

    shadowColor: "#000",

    shadowOpacity: 0.02,

    shadowRadius: 5,

    shadowOffset: {
      width: 0,
      height: 3,
    },

    elevation: 1,
  },

  activeMenuItem: {
    backgroundColor: "#173B8C",

    borderLeftWidth: 4,

    borderLeftColor: "#22C55E",
  },

  menuText: {
    flex: 1,

    marginLeft: 14,

    color: "#0F172A",

    fontWeight: "700",

    fontSize: 15,
  },

  activeMenuText: {
    color: "#FFFFFF",
  },

  bottomContainer: {
    paddingHorizontal: 20,

    paddingTop: 8,

    paddingBottom: 18,

    backgroundColor: "#F7F9FC",
  },

  logoutButton: {
    marginHorizontal: 20,

    marginTop: 10,

    height: 56,

    borderRadius: 18,

    backgroundColor: "#FFF5F5",

    flexDirection: "row",

    justifyContent: "center",

    alignItems: "center",
  },

  logoutText: {
    marginLeft: 10,

    color: "#EF4444",

    fontWeight: "700",

    fontSize: 16,
  },

  version: {
    marginTop: 22,

    marginBottom: 20,

    textAlign: "center",

    color: "#94A3B8",

    fontSize: 12,
  },

});
=======
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
import THEME from "../../constants/theme";

export default function AdminDrawerContent(props) {
  const { navigation, state } = props;
  const { signOut } = useAuth();

  const drawerRoute = state.routes[state.index];

  const activeRoute =
    getFocusedRouteNameFromRoute(drawerRoute) ??
    drawerRoute.name;

  const handleLogout = () => {
    signOut();
  };

  // ─────────────────────────────────────────────────────────────
  //  Menu items — mirrors the web Sidebar (Sidebar.jsx)
  //  so the mobile drawer and web drawer stay perfectly in sync.
  //  Bottom-tab quick-access items (Dashboard, Employees,
  //  Attendance, Analytics, Settings) are a subset of these,
  //  so nothing is duplicated between the two navigation layers.
  // ─────────────────────────────────────────────────────────────
  const menuItems = [
    // OVERVIEW
    {
      title: "Dashboard",
      icon: "home-outline",
      iconFocused: "home",
      route: "Dashboard",
      section: "OVERVIEW",
    },

    // HR MANAGEMENT
    {
      title: "Employees",
      icon: "people-outline",
      iconFocused: "people",
      route: "Employees",
      section: "HR MANAGEMENT",
    },
    {
      title: "Attendance",
      icon: "calendar-outline",
      iconFocused: "calendar",
      route: "Attendance",
      section: "HR MANAGEMENT",
    },
    {
      title: "Salary & Payslips",
      icon: "wallet-outline",
      iconFocused: "wallet",
      route: "Payroll",
      section: "HR MANAGEMENT",
    },
    {
      title: "Leaves & Holidays",
      icon: "calendar-clear-outline",
      iconFocused: "calendar-clear",
      route: "LeaveRequests",
      section: "HR MANAGEMENT",
    },

    // REPORTING
    {
      title: "Analytics",
      icon: "bar-chart-outline",
      iconFocused: "bar-chart",
      route: "Analytics",
      section: "REPORTING",
    },

    // SYSTEM
    {
      title: "Settings",
      icon: "settings-outline",
      iconFocused: "settings",
      route: "Settings",
      section: "SYSTEM",
    },
  ];

  const renderMenuItem = (item) => {
    const active = activeRoute === item.route;

    return (
      <TouchableOpacity
        key={item.title}
        activeOpacity={0.85}
        style={[
          styles.menuItem,
          active && styles.activeMenuItem,
        ]}
        onPress={() => {
          navigation.navigate("AdminTabs", {
            screen: item.route,
          });
          navigation.closeDrawer();
        }}
      >
        <Ionicons
          name={active ? item.iconFocused : item.icon}
          size={22}
          color={active ? "#FFFFFF" : "#173B8C"}
        />

        <Text
          style={[
            styles.menuText,
            active && styles.activeMenuText,
          ]}
        >
          {item.title}
        </Text>

        <Ionicons
          name="chevron-forward"
          size={18}
          color={active ? "#FFFFFF" : "#94A3B8"}
        />
      </TouchableOpacity>
    );
  };

  const renderSection = (title, section) => {
    const items = menuItems.filter(
      (item) => item.section === section
    );

    if (items.length === 0) return null;

    return (
      <View style={styles.section}>
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
            <Ionicons
              name="shield-checkmark"
              size={42}
              color="#173B8C"
            />
            <View style={styles.onlineDot} />
          </View>

          <Text style={styles.name}>Administrator</Text>

          <View style={styles.roleBadge}>
            <Text style={styles.roleText}>
              Super Administrator
            </Text>
          </View>

          <Text style={styles.empId}>ADMIN001</Text>
        </View>

        <View style={styles.divider} />

        {renderSection("OVERVIEW", "OVERVIEW")}
        {renderSection("HR MANAGEMENT", "HR MANAGEMENT")}
        {renderSection("REPORTING", "REPORTING")}
        {renderSection("SYSTEM", "SYSTEM")}
      </DrawerContentScrollView>

      {/* Bottom */}
      <View style={styles.bottomContainer}>
        <TouchableOpacity
          activeOpacity={0.85}
          style={styles.logoutButton}
          onPress={handleLogout}
        >
          <Ionicons
            name="log-out-outline"
            size={22}
            color="#EF4444"
          />
          <Text style={styles.logoutText}>Logout</Text>
        </TouchableOpacity>

        <Text style={styles.version}>Version 1.0.0</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F7F9FC",
  },

  scrollContent: {
    paddingBottom: 12,
  },

  header: {
    alignItems: "center",
    paddingTop: 8,
    paddingBottom: 12,
    paddingHorizontal: 24,
    backgroundColor: "#FFFFFF",
  },

  avatar: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: "#EEF4FF",
    justifyContent: "center",
    alignItems: "center",
    position: "relative",
    shadowColor: "#000",
    shadowOpacity: 0.08,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 5 },
    elevation: 4,
  },

  onlineDot: {
    position: "absolute",
    bottom: 8,
    right: 8,
    width: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: "#22C55E",
    borderWidth: 3,
    borderColor: "#FFFFFF",
  },

  name: {
    marginTop: 16,
    fontSize: 21,
    fontWeight: "800",
    color: "#0F172A",
  },

  roleBadge: {
    marginTop: 12,
    backgroundColor: "#EEF4FF",
    paddingHorizontal: 16,
    paddingVertical: 5,
    borderRadius: 30,
  },

  roleText: {
    color: "#173B8C",
    fontWeight: "700",
    fontSize: 13,
  },

  empId: {
    marginTop: 10,
    color: "#94A3B8",
    fontSize: 13,
    fontWeight: "600",
  },

  divider: {
    height: 1,
    backgroundColor: "#EEF2F7",
    marginVertical: 12,
    marginHorizontal: 20,
  },

  section: {
    marginBottom: 10,
    paddingHorizontal: 16,
  },

  sectionTitle: {
    marginBottom: 6,
    marginLeft: 8,
    fontSize: 11,
    fontWeight: "700",
    color: "#94A3B8",
    letterSpacing: 1.2,
  },

  menuItem: {
    height: 48,
    borderRadius: 14,
    paddingHorizontal: 16,
    marginBottom: 6,
    backgroundColor: "#FFFFFF",
    flexDirection: "row",
    alignItems: "center",
    shadowColor: "#000",
    shadowOpacity: 0.02,
    shadowRadius: 5,
    shadowOffset: { width: 0, height: 3 },
    elevation: 1,
  },

  activeMenuItem: {
    backgroundColor: "#173B8C",
    borderLeftWidth: 4,
    borderLeftColor: "#22C55E",
  },

  menuText: {
    flex: 1,
    marginLeft: 14,
    color: "#0F172A",
    fontWeight: "700",
    fontSize: 15,
  },

  activeMenuText: {
    color: "#FFFFFF",
  },

  bottomContainer: {
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 18,
    backgroundColor: "#F7F9FC",
  },

  logoutButton: {
    marginHorizontal: 20,
    marginTop: 10,
    height: 56,
    borderRadius: 18,
    backgroundColor: "#FFF5F5",
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
  },

  logoutText: {
    marginLeft: 10,
    color: "#EF4444",
    fontWeight: "700",
    fontSize: 16,
  },

  version: {
    marginTop: 22,
    marginBottom: 20,
    textAlign: "center",
    color: "#94A3B8",
    fontSize: 12,
  },
});
>>>>>>> 6dbd917e (Update admin attendance and payroll screens)
