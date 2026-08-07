import React, { useState } from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  View,
  Text,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from "react-native";
import { DrawerActions } from "@react-navigation/native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import THEME from "../../constants/theme";
import AdminHeader from "../../components/admin/AdminHeader";
import AdminSearchBar from "../../components/admin/AdminSearchBar";

import { fetchOnboarding } from "../../api/client";

export default function OnboardingScreen({ navigation }) {
  const [search, setSearch] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [onboardings, setOnboardings] = useState([]);

  const loadData = async () => {
    try {
      const res = await fetchOnboarding();
      if (res?.data?.ok && Array.isArray(res.data.onboardings)) {
        setOnboardings(res.data.onboardings);
      } else {
        setOnboardings([]);
      }
    } catch {
      setOnboardings([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  React.useEffect(() => {
    loadData();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const filteredOnboardings = onboardings.filter(
    (o) =>
      o.employeeName.toLowerCase().includes(search.toLowerCase()) ||
      o.role.toLowerCase().includes(search.toLowerCase())
  );

  const activeCount = onboardings.length;
  const totalTasks = onboardings.reduce((sum, item) => sum + Number(item.totalTasks || 0), 0);
  const completedTasks = onboardings.reduce((sum, item) => sum + Number(item.tasksCompleted || 0), 0);
  const avgProgress = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

  return (
    <LinearGradient
      colors={["#F8FAFC", "#F1F5F9", "#E2E8F0"]}
      style={styles.container}
    >
      <SafeAreaView style={{ flex: 1 }}>
        <AdminHeader
          title="Onboarding & Tasks"
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
          {/* Summary Hero Card */}
          <LinearGradient
            colors={["#0B2253", "#173B8C"]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.heroCard}
          >
            <Text style={styles.heroSub}>New Hire Workflow</Text>
            <Text style={styles.heroTitle}>{activeCount} Active Onboardings</Text>
            <View style={styles.heroStatsRow}>
              <View style={styles.heroStatItem}>
                <Text style={styles.heroStatValue}>{completedTasks} / {totalTasks}</Text>
                <Text style={styles.heroStatLabel}>Tasks Done</Text>
              </View>
              <View style={styles.heroStatDivider} />
              <View style={styles.heroStatItem}>
                <Text style={styles.heroStatValue}>{avgProgress}%</Text>
                <Text style={styles.heroStatLabel}>Avg Progress</Text>
              </View>
            </View>
          </LinearGradient>

          <AdminSearchBar
            value={search}
            onChangeText={setSearch}
            placeholder="Search new hires..."
          />

          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Onboarding Pipeline</Text>
            <Text style={styles.sectionBadge}>
              {filteredOnboardings.length} Active
            </Text>
          </View>

          {loading ? (
            <ActivityIndicator size="large" color="#173B8C" style={{ marginTop: 24 }} />
          ) : filteredOnboardings.length === 0 ? (
            <View style={{ backgroundColor: "#FFFFFF", borderRadius: 16, padding: 32, alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: "#E2E8F0", marginTop: 10 }}>
              <Ionicons name="person-add-outline" size={48} color="#94A3B8" />
              <Text style={{ fontSize: 16, fontWeight: "700", color: "#334155", marginTop: 12 }}>
                No Active Onboardings
              </Text>
              <Text style={{ fontSize: 13, color: "#64748B", textAlign: "center", marginTop: 4 }}>
                Newly registered staff members undergoing onboarding tasks will appear here.
              </Text>
            </View>
          ) : (
            filteredOnboardings.map((item) => {
              const progress = (item.tasksCompleted / item.totalTasks) * 100;

              return (
                <View key={item.id} style={styles.card}>
                  <View style={styles.cardHeader}>
                    <View style={styles.iconCircle}>
                      <Ionicons name="person-add-outline" size={20} color="#173B8C" />
                    </View>
                    <View style={{ flex: 1, marginLeft: 12 }}>
                      <Text style={styles.name}>{item.employeeName}</Text>
                      <Text style={styles.role}>{item.role}</Text>
                    </View>
                    <View
                      style={[
                        styles.statusPill,
                        item.status === "Completed"
                          ? styles.pillCompleted
                          : item.status === "In Progress"
                          ? styles.pillProgress
                          : styles.pillPending,
                      ]}
                    >
                      <Text
                        style={[
                          styles.statusText,
                          item.status === "Completed"
                            ? styles.textCompleted
                            : item.status === "In Progress"
                            ? styles.textProgress
                            : styles.textPending,
                        ]}
                      >
                        {item.status}
                      </Text>
                    </View>
                  </View>

                  <View style={styles.progressContainer}>
                    <View style={styles.progressLabelRow}>
                      <Text style={styles.progressLabel}>Task Completion</Text>
                      <Text style={styles.progressValue}>
                        {item.tasksCompleted} / {item.totalTasks} ({progress.toFixed(0)}%)
                      </Text>
                    </View>
                    <View style={styles.progressBarTrack}>
                      <View
                        style={[
                          styles.progressBarFill,
                          { width: `${progress}%` },
                        ]}
                      />
                    </View>
                  </View>

                  <View style={styles.cardFooter}>
                    <Ionicons name="calendar-outline" size={14} color="#64748B" />
                    <Text style={styles.footerText}>
                      Join Date: {item.startDate}
                    </Text>
                  </View>
                </View>
              );
            })
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
  heroCard: {
    backgroundColor: "#1E293B",
    borderRadius: 24,
    padding: 20,
    marginBottom: 18,
    elevation: 4,
  },
  heroSub: { color: "#94A3B8", fontSize: 13, fontWeight: "600" },
  heroTitle: { color: "#FFFFFF", fontSize: 22, fontWeight: "800", marginTop: 4 },
  heroStatsRow: {
    flexDirection: "row",
    justifyContent: "space-around",
    marginTop: 18,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: "rgba(255,255,255,0.1)",
  },
  heroStatItem: { alignItems: "center" },
  heroStatValue: { color: "#60A5FA", fontSize: 18, fontWeight: "800" },
  heroStatLabel: { color: "#94A3B8", fontSize: 12, marginTop: 2 },
  heroStatDivider: { width: 1, height: 28, backgroundColor: "rgba(255,255,255,0.1)" },
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 18,
    marginBottom: 12,
  },
  sectionTitle: { fontSize: 18, fontWeight: "800", color: "#0F172A" },
  sectionBadge: { fontSize: 13, fontWeight: "700", color: "#173B8C" },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 16,
    marginBottom: 12,
    elevation: 2,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  cardHeader: { flexDirection: "row", alignItems: "center" },
  iconCircle: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: "#EFF6FF",
    justifyContent: "center",
    alignItems: "center",
  },
  name: { fontSize: 16, fontWeight: "700", color: "#0F172A" },
  role: { fontSize: 13, color: "#64748B", marginTop: 2 },
  statusPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  pillCompleted: { backgroundColor: "#DCFCE7" },
  pillProgress: { backgroundColor: "#E0F2FE" },
  pillPending: { backgroundColor: "#FEF3C7" },
  statusText: { fontSize: 11, fontWeight: "700" },
  textCompleted: { color: "#166534" },
  textProgress: { color: "#075985" },
  textPending: { color: "#B45309" },
  progressContainer: { marginTop: 14 },
  progressLabelRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: 6 },
  progressLabel: { fontSize: 12, color: "#64748B", fontWeight: "600" },
  progressValue: { fontSize: 12, color: "#0F172A", fontWeight: "700" },
  progressBarTrack: { height: 8, backgroundColor: "#F1F5F9", borderRadius: 4, overflow: "hidden" },
  progressBarFill: { height: "100%", backgroundColor: "#3B82F6", borderRadius: 4 },
  cardFooter: { flexDirection: "row", alignItems: "center", marginTop: 12, paddingTop: 10, borderTopWidth: 1, borderTopColor: "#F8FAFC" },
  footerText: { marginLeft: 6, fontSize: 12, color: "#64748B" },
});
