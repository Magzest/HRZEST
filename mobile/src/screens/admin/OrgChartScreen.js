import React, { useState, useEffect, useCallback } from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  View,
  Text,
  RefreshControl,
  ActivityIndicator,
} from "react-native";
import { DrawerActions } from "@react-navigation/native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import THEME from "../../constants/theme";
import AdminHeader from "../../components/admin/AdminHeader";
import { fetchDepartments, fetchEmployees, fetchDashboard } from "../../api/client";

// /api/org_chart_data exists but is session-cookie-only (@admin_required),
// not reachable with a mobile Bearer token. Rather than show the invented
// "Sarah Jenkins (VP Eng)" / fake team tags this screen used to, it builds
// a real (if simpler) org view from /api/departments + /api/employees,
// which are both genuinely Bearer-compatible.
export default function OrgChartScreen({ navigation }) {
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [departments, setDepartments] = useState([]);
  const [employeesByDept, setEmployeesByDept] = useState({});
  const [companyName, setCompanyName] = useState("");
  const [totalStaff, setTotalStaff] = useState(0);

  const load = useCallback(async () => {
    try {
      const [deptRes, empRes, dashRes] = await Promise.all([
        fetchDepartments(),
        fetchEmployees(),
        fetchDashboard().catch(() => null),
      ]);
      const depts = deptRes?.data?.ok ? deptRes.data.departments : [];
      setDepartments(depts);

      const employees = empRes?.data?.employees || [];
      setTotalStaff(employees.length);
      const grouped = {};
      employees.forEach((e) => {
        const dept = e.department || "Unassigned";
        if (!grouped[dept]) grouped[dept] = [];
        grouped[dept].push(e.name || e.employee_id);
      });
      setEmployeesByDept(grouped);

      setCompanyName(dashRes?.data?.company_name || "");
    } catch (_) {
      setDepartments([]);
      setEmployeesByDept({});
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    load().finally(() => setLoading(false));
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
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
          {/* Company Summary Box */}
          <View style={styles.execCard}>
            <View style={styles.execBadge}>
              <Text style={styles.execBadgeText}>ORGANIZATION</Text>
            </View>
            <Text style={styles.execName}>{companyName || "Your Company"}</Text>
            <View style={styles.execStats}>
              <Text style={styles.execStatsText}>
                {totalStaff} Total Staff • {departments.length} Departments
              </Text>
            </View>
          </View>

          <View style={styles.treeConnector} />

          {/* Department List */}
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Departments</Text>
          </View>

          {loading ? (
            <ActivityIndicator size="large" color="#173B8C" style={{ marginTop: 20 }} />
          ) : departments.length === 0 ? (
            <View style={styles.emptyCard}>
              <Ionicons name="business-outline" size={40} color="#94A3B8" />
              <Text style={styles.emptyText}>No departments found yet.</Text>
            </View>
          ) : (
            departments.map((dept, index) => (
              <View key={index} style={styles.deptCard}>
                <View style={styles.deptHeader}>
                  <View style={styles.deptIconBadge}>
                    <Ionicons name="briefcase-outline" size={20} color="#173B8C" />
                  </View>
                  <View style={{ flex: 1, marginLeft: 12 }}>
                    <Text style={styles.deptName}>{dept.name}</Text>
                  </View>
                  <View style={styles.countBadge}>
                    <Text style={styles.countText}>{dept.count} Staff</Text>
                  </View>
                </View>

                {employeesByDept[dept.name]?.length > 0 && (
                  <>
                    <View style={styles.divider} />
                    <Text style={styles.teamsLabel}>Team Members</Text>
                    <View style={styles.teamsWrap}>
                      {employeesByDept[dept.name].slice(0, 8).map((name, idx) => (
                        <View key={idx} style={styles.teamTag}>
                          <Text style={styles.teamTagText}>{name}</Text>
                        </View>
                      ))}
                      {employeesByDept[dept.name].length > 8 && (
                        <View style={styles.teamTag}>
                          <Text style={styles.teamTagText}>
                            +{employeesByDept[dept.name].length - 8} more
                          </Text>
                        </View>
                      )}
                    </View>
                  </>
                )}
              </View>
            ))
          )}

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
  emptyCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 32,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  emptyText: { marginTop: 10, fontSize: 13, color: "#64748B", fontWeight: "600" },
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
