import React, { useState } from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  View,
  Text,
  TouchableOpacity,
  RefreshControl,
} from "react-native";
import { DrawerActions } from "@react-navigation/native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import THEME from "../../constants/theme";
import AdminHeader from "../../components/admin/AdminHeader";

export default function OrgChartScreen({ navigation }) {
  const [refreshing, setRefreshing] = useState(false);

  const departments = [
    {
      name: "Engineering & Product",
      head: "Sarah Jenkins (VP Eng)",
      members: 42,
      teams: ["Frontend", "Backend", "DevOps", "QA"],
    },
    {
      name: "Human Resources",
      head: "Emily Watson (HR Director)",
      members: 12,
      teams: ["Recruitment", "Payroll & Ops", "Employee Relations"],
    },
    {
      name: "Finance & Accounts",
      head: "Robert Garcia (CFO)",
      members: 8,
      teams: ["Payroll", "Audit", "Billing"],
    },
    {
      name: "Sales & Marketing",
      head: "Jessica Alba (CMO)",
      members: 24,
      teams: ["Digital Marketing", "Enterprise Sales"],
    },
  ];

  const onRefresh = () => {
    setRefreshing(true);
    setTimeout(() => {
      setRefreshing(false);
    }, 1000);
  };

  return (
    <LinearGradient
      colors={["#F8FAFC", "#F1F5F9", "#E2E8F0"]}
      style={styles.container}
    >
      <SafeAreaView style={{ flex: 1 }}>
        <AdminHeader
          title="Organization Chart"
          onMenu={() => navigation.dispatch(DrawerActions.openDrawer())}
        />

        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.content}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              colors={[THEME.colors.primary]}
            />
          }
        >
          {/* Executive Leadership Box */}
          <View style={styles.execCard}>
            <View style={styles.execBadge}>
              <Text style={styles.execBadgeText}>CHIEF EXECUTIVE OFFICER</Text>
            </View>
            <Text style={styles.execName}>Super Administrator</Text>
            <Text style={styles.execCompany}>HR Management System</Text>
            <View style={styles.execStats}>
              <Text style={styles.execStatsText}>86 Total Staff • 4 Departments</Text>
            </View>
          </View>

          <View style={styles.treeConnector} />

          {/* Department List */}
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Departments Hierarchy</Text>
          </View>

          {departments.map((dept, index) => (
            <View key={index} style={styles.deptCard}>
              <View style={styles.deptHeader}>
                <View style={styles.deptIconBadge}>
                  <Ionicons name="briefcase-outline" size={20} color="#173B8C" />
                </View>
                <View style={{ flex: 1, marginLeft: 12 }}>
                  <Text style={styles.deptName}>{dept.name}</Text>
                  <Text style={styles.deptHead}>Lead: {dept.head}</Text>
                </View>
                <View style={styles.countBadge}>
                  <Text style={styles.countText}>{dept.members} Staff</Text>
                </View>
              </View>

              <View style={styles.divider} />

              <Text style={styles.teamsLabel}>Teams & Sub-groups</Text>
              <View style={styles.teamsWrap}>
                {dept.teams.map((t, idx) => (
                  <View key={idx} style={styles.teamTag}>
                    <Text style={styles.teamTagText}>{t}</Text>
                  </View>
                ))}
              </View>
            </View>
          ))}

          <View style={{ height: 100 }} />
        </ScrollView>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { paddingHorizontal: 20, paddingTop: 10 },
  execCard: {
    backgroundColor: "#173B8C",
    borderRadius: 24,
    padding: 20,
    alignItems: "center",
    elevation: 4,
  },
  execBadge: {
    backgroundColor: "rgba(255,255,255,0.15)",
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
    marginBottom: 8,
  },
  execBadgeText: { color: "#93C5FD", fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  execName: { color: "#FFFFFF", fontSize: 16, fontWeight: "800" },
  execCompany: { color: "rgba(255,255,255,0.7)", fontSize: 12, marginTop: 2 },
  execStats: { marginTop: 14, paddingTop: 10, borderTopWidth: 1, borderTopColor: "rgba(255,255,255,0.15)" },
  execStatsText: { color: "#FFFFFF", fontSize: 12, fontWeight: "600" },
  treeConnector: {
    width: 2,
    height: 24,
    backgroundColor: "#CBD5E1",
    alignSelf: "center",
    marginVertical: 4,
  },
  sectionHeader: { marginBottom: 12 },
  sectionTitle: { fontSize: 14, fontWeight: "800", color: "#0F172A" },
  deptCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 16,
    marginBottom: 12,
    elevation: 2,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  deptHeader: { flexDirection: "row", alignItems: "center" },
  deptIconBadge: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: "#EEF4FF",
    justifyContent: "center",
    alignItems: "center",
  },
  deptName: { fontSize: 13, fontWeight: "700", color: "#0F172A" },
  deptHead: { fontSize: 13, color: "#64748B", marginTop: 2 },
  countBadge: {
    backgroundColor: "#F1F5F9",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 12,
  },
  countText: { fontSize: 12, fontWeight: "700", color: "#334155" },
  divider: { height: 1, backgroundColor: "#F1F5F9", marginVertical: 12 },
  teamsLabel: { fontSize: 11, fontWeight: "700", color: "#94A3B8", letterSpacing: 0.5 },
  teamsWrap: { flexDirection: "row", flexWrap: "wrap", marginTop: 8 },
  teamTag: {
    backgroundColor: "#EFF6FF",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 10,
    marginRight: 6,
    marginBottom: 6,
  },
  teamTagText: { fontSize: 12, fontWeight: "600", color: "#1D4ED8" },
});
