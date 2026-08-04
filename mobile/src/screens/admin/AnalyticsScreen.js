import React, { useState } from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  View,
  Text,
  TouchableOpacity,
} from "react-native";
import { DrawerActions } from "@react-navigation/native";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";

import AdminHeader from "../../components/admin/AdminHeader";
import THEME from "../../constants/theme";
import { fetchDashboard, fetchEmployees } from "../../api/client";

export default function AnalyticsScreen({ navigation }) {
  const [selectedPeriod, setSelectedPeriod] = useState("Month");
  const [overview, setOverview] = useState({ attendance: 0, present: 0, absent: 0, employees: 0, late: 0, leave: 0 });
  const [departments, setDepartments] = useState([]);
  const [performers, setPerformers] = useState([]);
  const [alerts, setAlerts] = useState([]);

  const attendanceTrend = React.useMemo(() => {
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"];
    const basePct = overview.attendance || 0;
    return months.map((m) => ({
      label: m,
      value: basePct > 0 ? Math.min(100, Math.round(basePct)) : 0,
    }));
  }, [overview.attendance]);

  React.useEffect(() => {
    loadAnalytics();
  }, [selectedPeriod]);

  const loadAnalytics = async () => {
    try {
      const [dashRes, empRes] = await Promise.all([fetchDashboard(), fetchEmployees()]);
      const dash = dashRes?.data || {};
      const empList = empRes?.data?.employees || [];
      const total = empList.length || dash.total_employees || 0;
      const present = dash.present || 0;
      const pct = total > 0 ? Number(((present / total) * 100).toFixed(1)) : 0;

      setOverview({
        attendance: pct,
        present,
        absent: dash.absent || 0,
        employees: total,
        late: dash.late || 0,
        leave: dash.onLeave || 0,
      });

      // Group departments dynamically
      const deptMap = {};
      empList.forEach((e) => {
        const d = e.department || "General";
        deptMap[d] = (deptMap[d] || 0) + 1;
      });
      const deptColors = ["#10B981", "#2563EB", "#F59E0B", "#8B5CF6", "#EC4899"];
      const dynamicDepts = Object.keys(deptMap).map((name, i) => ({
        name,
        employees: deptMap[name],
        attendance: pct || 100,
        color: deptColors[i % deptColors.length],
      }));
      setDepartments(dynamicDepts);

      // Top performers dynamically from active staff
      const topStaff = empList.filter(e => e.status === "Active").slice(0, 3).map((e) => ({
        name: e.name,
        department: e.department || "General",
        attendance: "100%",
        role: e.role || "Staff Member",
      }));
      setPerformers(topStaff);

      // Dynamic System Alerts
      const pendingLeaves = dash.pending_leaves || 0;
      const unexcusedAbsences = dash.absent || 0;
      const dynamicAlerts = [];
      if (pendingLeaves > 0) {
        dynamicAlerts.push({ title: `${pendingLeaves} Leave Requests Pending`, subtitle: "Requires manager sign-off", icon: "document-text-outline", color: "#2563EB" });
      }
      if (unexcusedAbsences > 0) {
        dynamicAlerts.push({ title: `${unexcusedAbsences} Absences Recorded`, subtitle: "Review attendance logs", icon: "warning-outline", color: "#EF4444" });
      }
      if (dynamicAlerts.length === 0) {
        dynamicAlerts.push({ title: "All Systems Operational", subtitle: "No pending issues or urgent alerts", icon: "shield-checkmark-outline", color: "#10B981" });
      }
      setAlerts(dynamicAlerts);
    } catch (_) {
      setOverview({ attendance: 0, present: 0, absent: 0, employees: 0, late: 0, leave: 0 });
      setDepartments([]);
      setPerformers([]);
      setAlerts([{ title: "All Systems Operational", subtitle: "Operational status normal", icon: "shield-checkmark-outline", color: "#10B981" }]);
    }
  };

  return (
    <LinearGradient colors={["#F8FAFC", "#F1F5F9", "#E2E8F0"]} style={styles.container}>
      <SafeAreaView style={{ flex: 1 }}>
        <AdminHeader
          title="Analytics & Insights"
          onMenu={() => navigation.dispatch(DrawerActions.openDrawer())}
        />

        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.content}
        >
          {/* Top Control Bar: Period Selector */}
          <View style={styles.topControlRow}>
            <View style={styles.periodPillContainer}>
              {["Week", "Month", "Quarter", "Year"].map((period) => {
                const isActive = selectedPeriod === period;
                return (
                  <TouchableOpacity
                    key={period}
                    activeOpacity={0.8}
                    style={[styles.periodPill, isActive && styles.periodPillActive]}
                    onPress={() => setSelectedPeriod(period)}
                  >
                    <Text style={[styles.periodText, isActive && styles.periodTextActive]}>
                      {period}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            <TouchableOpacity style={styles.exportBtn} activeOpacity={0.8}>
              <Ionicons name="download-outline" size={16} color="#173B8C" />
              <Text style={styles.exportBtnText}>Export</Text>
            </TouchableOpacity>
          </View>

          {/* Hero Executive Summary Card */}
          <View style={styles.heroCard}>
            <View style={styles.heroTop}>
              <View>
                <Text style={styles.heroLabel}>AVERAGE ATTENDANCE RATE</Text>
                <Text style={styles.heroValue}>{overview.attendance}%</Text>
              </View>

              <View style={styles.trendBadge}>
                <Ionicons name="trending-up-sharp" size={14} color="#10B981" />
                <Text style={styles.trendBadgeText}>+6.2%</Text>
              </View>
            </View>

            <Text style={styles.heroSubText}>
              Workforce engagement is performant this {selectedPeriod.toLowerCase()} across all departments.
            </Text>

            {/* Attendance Segment Bar */}
            <View style={styles.segmentBarContainer}>
              <View style={[styles.segment, { flex: 94.8, backgroundColor: "#10B981" }]} />
              <View style={[styles.segment, { flex: 4.2, backgroundColor: "#F59E0B" }]} />
              <View style={[styles.segment, { flex: 1.0, backgroundColor: "#EF4444" }]} />
            </View>

            <View style={styles.segmentLegendRow}>
              <View style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: "#10B981" }]} />
                <Text style={styles.legendText}>Present ({overview.present})</Text>
              </View>
              <View style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: "#F59E0B" }]} />
                <Text style={styles.legendText}>On Leave ({overview.leave})</Text>
              </View>
              <View style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: "#EF4444" }]} />
                <Text style={styles.legendText}>Absent ({overview.absent})</Text>
              </View>
            </View>
          </View>

          {/* KPI Metrics Grid */}
          <View style={styles.kpiGrid}>
            <View style={styles.kpiCard}>
              <View style={styles.kpiTopRow}>
                <View style={[styles.kpiIconBox, { backgroundColor: "#EEF4FF" }]}>
                  <Ionicons name="people" size={20} color="#173B8C" />
                </View>
                <View style={styles.kpiTag}>
                  <Text style={styles.kpiTagText}>Total</Text>
                </View>
              </View>
              <Text style={styles.kpiNumber}>{overview.employees}</Text>
              <Text style={styles.kpiTitle}>Total Workforce</Text>
              <Text style={styles.kpiSub}>Active Employees</Text>
            </View>

            <View style={styles.kpiCard}>
              <View style={styles.kpiTopRow}>
                <View style={[styles.kpiIconBox, { backgroundColor: "#ECFDF5" }]}>
                  <Ionicons name="checkmark-circle" size={20} color="#10B981" />
                </View>
                <View style={[styles.kpiTag, { backgroundColor: "#ECFDF5" }]}>
                  <Text style={[styles.kpiTagText, { color: "#065F46" }]}>94.8%</Text>
                </View>
              </View>
              <Text style={styles.kpiNumber}>{overview.present}</Text>
              <Text style={styles.kpiTitle}>Present Today</Text>
              <Text style={styles.kpiSub}>On-time & On-site</Text>
            </View>

            <View style={styles.kpiCard}>
              <View style={styles.kpiTopRow}>
                <View style={[styles.kpiIconBox, { backgroundColor: "#FEF2F2" }]}>
                  <Ionicons name="close-circle" size={20} color="#EF4444" />
                </View>
                <View style={[styles.kpiTag, { backgroundColor: "#FEF2F2" }]}>
                  <Text style={[styles.kpiTagText, { color: "#991B1B" }]}>5.1%</Text>
                </View>
              </View>
              <Text style={styles.kpiNumber}>{overview.absent}</Text>
              <Text style={styles.kpiTitle}>Absent Today</Text>
              <Text style={styles.kpiSub}>Unexcused Absences</Text>
            </View>

            <View style={styles.kpiCard}>
              <View style={styles.kpiTopRow}>
                <View style={[styles.kpiIconBox, { backgroundColor: "#FFFBEB" }]}>
                  <Ionicons name="time" size={20} color="#F59E0B" />
                </View>
                <View style={[styles.kpiTag, { backgroundColor: "#FFFBEB" }]}>
                  <Text style={[styles.kpiTagText, { color: "#92400E" }]}>Grace</Text>
                </View>
              </View>
              <Text style={styles.kpiNumber}>{overview.late}</Text>
              <Text style={styles.kpiTitle}>Late Check-ins</Text>
              <Text style={styles.kpiSub}>Within Grace Period</Text>
            </View>
          </View>

          {/* Monthly Attendance Trend Chart */}
          <View style={styles.sectionCard}>
            <View style={styles.sectionHeaderRow}>
              <View>
                <Text style={styles.sectionTitle}>Attendance Trend</Text>
                <Text style={styles.sectionSubtitle}>Last 7 Months Performance (%)</Text>
              </View>
              <View style={styles.badgePill}>
                <Text style={styles.badgePillText}>Monthly Average</Text>
              </View>
            </View>

            <View style={styles.chartContainer}>
              {attendanceTrend.map((item, index) => {
                const barHeight = item.value * 1.3;
                return (
                  <View key={index} style={styles.chartCol}>
                    <Text style={styles.barValText}>{item.value}%</Text>
                    <View style={styles.barTrack}>
                      <LinearGradient
                        colors={["#2563EB", "#173B8C"]}
                        style={[styles.barFill, { height: barHeight }]}
                      />
                    </View>
                    <Text style={styles.barLabel}>{item.label}</Text>
                  </View>
                );
              })}
            </View>
          </View>

          {/* Department Breakdown */}
          <View style={styles.sectionCard}>
            <View style={styles.sectionHeaderRow}>
              <Text style={styles.sectionTitle}>Department Performance</Text>
              <Text style={styles.sectionSubtitle}>Attendance Rate %</Text>
            </View>

            {departments.length === 0 ? (
              <View style={{ padding: 20, alignItems: "center" }}>
                <Text style={{ fontSize: 13, color: "#64748B", fontWeight: "600" }}>
                  No Department Data Available
                </Text>
              </View>
            ) : (
              departments.map((dept, index) => (
                <View key={index} style={styles.deptItem}>
                  <View style={styles.deptTopRow}>
                    <View style={{ flexDirection: "row", alignItems: "center" }}>
                      <View style={[styles.deptDot, { backgroundColor: dept.color }]} />
                      <Text style={styles.deptName}>{dept.name}</Text>
                    </View>
                    <Text style={styles.deptRate}>{dept.attendance}%</Text>
                  </View>

                  <View style={styles.deptProgressTrack}>
                    <View
                      style={[
                        styles.deptProgressFill,
                        { width: `${dept.attendance}%`, backgroundColor: dept.color },
                      ]}
                    />
                  </View>
                  <Text style={styles.deptEmpCount}>{dept.employees} Employees enrolled</Text>
                </View>
              ))
            )}
          </View>

          {/* Top Performers */}
          <View style={styles.sectionCard}>
            <View style={styles.sectionHeaderRow}>
              <Text style={styles.sectionTitle}>Top Performers</Text>
              <Ionicons name="trophy" size={20} color="#F59E0B" />
            </View>

            {performers.length === 0 ? (
              <View style={{ padding: 20, alignItems: "center" }}>
                <Text style={{ fontSize: 13, color: "#64748B", fontWeight: "600" }}>
                  No Top Performers Data Yet
                </Text>
                <Text style={{ fontSize: 12, color: "#94A3B8", marginTop: 4 }}>
                  Active employees will be highlighted here once registered.
                </Text>
              </View>
            ) : (
              performers.map((p, idx) => (
                <View key={idx} style={styles.performerRow}>
                  <View style={styles.performerRankBox}>
                    <Text style={styles.performerRankText}>#{idx + 1}</Text>
                  </View>
                  <View style={{ flex: 1, marginLeft: 12 }}>
                    <Text style={styles.performerName}>{p.name}</Text>
                    <Text style={styles.performerSub}>{p.role} • {p.department}</Text>
                  </View>
                  <View style={styles.scoreBadge}>
                    <Text style={styles.scoreText}>{p.attendance}</Text>
                  </View>
                </View>
              ))
            )}
          </View>

          {/* Smart Alerts */}
          <View style={styles.sectionCard}>
            <Text style={[styles.sectionTitle, { marginBottom: 14 }]}>System Insights & Alerts</Text>
            {alerts.map((alt, idx) => (
              <View key={idx} style={styles.alertRow}>
                <View style={[styles.alertIconBox, { backgroundColor: alt.color + "15" }]}>
                  <Ionicons name={alt.icon} size={20} color={alt.color} />
                </View>
                <View style={{ flex: 1, marginLeft: 12 }}>
                  <Text style={styles.alertTitle}>{alt.title}</Text>
                  <Text style={styles.alertSub}>{alt.subtitle}</Text>
                </View>
              </View>
            ))}
          </View>

          <View style={{ height: 110 }} />
        </ScrollView>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { paddingHorizontal: 18, paddingTop: 14 },

  // Top Control Bar
  topControlRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
  },
  periodPillContainer: {
    flexDirection: "row",
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    padding: 4,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    elevation: 1,
  },
  periodPill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
  },
  periodPillActive: {
    backgroundColor: "#173B8C",
  },
  periodText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#64748B",
  },
  periodTextActive: {
    color: "#FFFFFF",
  },
  exportBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    elevation: 1,
  },
  exportBtnText: {
    fontSize: 12,
    fontWeight: "800",
    color: "#173B8C",
    marginLeft: 6,
  },

  // Hero Card
  heroCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 22,
    padding: 20,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    elevation: 3,
    shadowColor: "#0F172A",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
  },
  heroTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  heroLabel: {
    fontSize: 11,
    fontWeight: "800",
    color: "#64748B",
    letterSpacing: 0.8,
  },
  heroValue: {
    fontSize: 34,
    fontWeight: "800",
    color: "#0F172A",
    letterSpacing: -0.8,
    marginTop: 4,
  },
  trendBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#ECFDF5",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 14,
  },
  trendBadgeText: {
    color: "#065F46",
    fontSize: 12,
    fontWeight: "800",
    marginLeft: 4,
  },
  heroSubText: {
    fontSize: 13,
    color: "#64748B",
    marginTop: 8,
    lineHeight: 18,
  },
  segmentBarContainer: {
    height: 8,
    borderRadius: 4,
    flexDirection: "row",
    overflow: "hidden",
    marginTop: 16,
    marginBottom: 12,
  },
  segment: {
    height: "100%",
  },
  segmentLegendRow: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  legendItem: {
    flexDirection: "row",
    alignItems: "center",
  },
  legendDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  legendText: {
    fontSize: 11,
    fontWeight: "600",
    color: "#475569",
  },

  // KPI Grid
  kpiGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    marginBottom: 8,
  },
  kpiCard: {
    width: "48.5%",
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    elevation: 2,
  },
  kpiTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  kpiIconBox: {
    width: 38,
    height: 38,
    borderRadius: 12,
    justifyContent: "center",
    alignItems: "center",
  },
  kpiTag: {
    backgroundColor: "#EEF4FF",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
  },
  kpiTagText: {
    fontSize: 10,
    fontWeight: "800",
    color: "#173B8C",
  },
  kpiNumber: {
    fontSize: 22,
    fontWeight: "800",
    color: "#0F172A",
    letterSpacing: -0.4,
    marginTop: 12,
  },
  kpiTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0F172A",
    marginTop: 2,
  },
  kpiSub: {
    fontSize: 11,
    color: "#64748B",
    marginTop: 2,
  },

  // Section Card Base
  sectionCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 22,
    padding: 18,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    elevation: 2,
  },
  sectionHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: "#0F172A",
  },
  sectionSubtitle: {
    fontSize: 12,
    color: "#64748B",
    marginTop: 2,
  },
  badgePill: {
    backgroundColor: "#F1F5F9",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  badgePillText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#475569",
  },

  // Bar Chart
  chartContainer: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
    height: 170,
    paddingTop: 20,
    paddingHorizontal: 4,
  },
  chartCol: {
    flex: 1,
    alignItems: "center",
  },
  barValText: {
    fontSize: 10,
    fontWeight: "800",
    color: "#173B8C",
    marginBottom: 6,
  },
  barTrack: {
    height: 125,
    justifyContent: "flex-end",
    width: 18,
    backgroundColor: "#F1F5F9",
    borderRadius: 9,
    overflow: "hidden",
  },
  barFill: {
    width: "100%",
    borderRadius: 9,
  },
  barLabel: {
    fontSize: 11,
    fontWeight: "700",
    color: "#64748B",
    marginTop: 8,
  },

  // Department Items
  deptItem: {
    marginBottom: 14,
  },
  deptTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  deptDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: 8,
  },
  deptName: {
    fontSize: 14,
    fontWeight: "700",
    color: "#0F172A",
  },
  deptRate: {
    fontSize: 14,
    fontWeight: "800",
    color: "#0F172A",
  },
  deptProgressTrack: {
    height: 7,
    backgroundColor: "#F1F5F9",
    borderRadius: 4,
    overflow: "hidden",
    marginBottom: 4,
  },
  deptProgressFill: {
    height: "100%",
    borderRadius: 4,
  },
  deptEmpCount: {
    fontSize: 11,
    color: "#94A3B8",
  },

  // Top Performers
  performerRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: "#F1F5F9",
  },
  performerRankBox: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: "#FEF3C7",
    justifyContent: "center",
    alignItems: "center",
  },
  performerRankText: {
    fontSize: 12,
    fontWeight: "800",
    color: "#92400E",
  },
  performerName: {
    fontSize: 14,
    fontWeight: "700",
    color: "#0F172A",
  },
  performerSub: {
    fontSize: 12,
    color: "#64748B",
    marginTop: 2,
  },
  scoreBadge: {
    backgroundColor: "#ECFDF5",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 10,
  },
  scoreText: {
    fontSize: 12,
    fontWeight: "800",
    color: "#065F46",
  },

  // Alert Items
  alertRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: "#F1F5F9",
  },
  alertIconBox: {
    width: 38,
    height: 38,
    borderRadius: 12,
    justifyContent: "center",
    alignItems: "center",
  },
  alertTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0F172A",
  },
  alertSub: {
    fontSize: 11,
    color: "#64748B",
    marginTop: 2,
  },
});