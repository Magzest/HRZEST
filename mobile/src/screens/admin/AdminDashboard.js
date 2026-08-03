import React, { useState, useCallback } from "react";
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
import { useFocusEffect } from "@react-navigation/native";

import THEME from "../../constants/theme";
import { fetchDashboard, fetchLeaveRequests } from "../../api/client";

import AdminHeader from "../../components/admin/AdminHeader";
import AdminSearchBar from "../../components/admin/AdminSearchBar";
import DashboardHeroCard from "../../components/admin/DashboardHeroCard";
import PendingApprovalCard from "../../components/admin/PendingApprovalCard";
import AttendanceOverviewCard from "../../components/admin/AttendanceOverviewCard";
import QuickActionGrid from "../../components/admin/QuickActionGrid";
import RecentActivityList from "../../components/admin/RecentActivityList";
import AnnouncementCard from "../../components/admin/AnnouncementCard";
import AnalyticsOverviewCard from "../../components/admin/AnalyticsOverviewCard";

export default function AdminDashboard({ navigation }) {
  const [search, setSearch] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [dashData, setDashData] = useState(null);
  const [pendingLeaves, setPendingLeaves] = useState(0);

  const loadData = async () => {
    try {
      const [dashRes, leaveRes] = await Promise.all([
        fetchDashboard(),
        fetchLeaveRequests(),
      ]);
      if (dashRes?.data?.ok) setDashData(dashRes.data);
      if (leaveRes?.data?.ok) {
        const pending = (leaveRes.data.leave_requests || []).filter(
          (r) => r.status === "Pending"
        ).length;
        setPendingLeaves(pending);
      }
    } catch {}
    setLoading(false);
    setRefreshing(false);
  };

  useFocusEffect(useCallback(() => { loadData(); }, []));

  const onRefresh = () => { setRefreshing(true); loadData(); };

  if (loading) {
    return (
      <LinearGradient colors={["#F8FAFC", "#F3F7FD", "#EDF4FF"]} style={styles.container}>
        <SafeAreaView style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
          <ActivityIndicator size="large" color={THEME.colors.primary} />
          <Text style={{ marginTop: 12, color: "#64748B", fontWeight: "600" }}>Loading dashboard…</Text>
        </SafeAreaView>
      </LinearGradient>
    );
  }

  return (
    <LinearGradient
      colors={["#F8FAFC", "#F3F7FD", "#EDF4FF"]}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={styles.container}
    >
      <SafeAreaView style={{ flex: 1 }}>
        <AdminHeader
          title="Dashboard"
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
          <DashboardHeroCard
            adminName={dashData?.admin_name || "Administrator"}
            company={dashData?.company_name || "HR Management System"}
            totalEmployees={dashData?.total ?? "--"}
            present={dashData?.present ?? "--"}
          />

          <AdminSearchBar
            value={search}
            onChangeText={setSearch}
            placeholder="Search employees..."
          />

          <View style={styles.sectionSpacing} />

          <AttendanceOverviewCard />

          <QuickActionGrid navigation={navigation} />

          <PendingApprovalCard
            title="Leave Requests"
            pending={pendingLeaves}
            subtitle={pendingLeaves > 0 ? "Requires your approval" : "All up to date"}
            icon="document-text-outline"
            color="#F59E0B"
            background="#FEF3C7"
          />

          <AnalyticsOverviewCard />
          <AnnouncementCard />
          <RecentActivityList />

          <View style={styles.bottomSpacing} />
        </ScrollView>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({

  container: {
    flex: 1,
  },

  content: {
    paddingHorizontal: 20,
    paddingBottom: 120,
  },

  sectionSpacing: {
    height: 20,
  },

  statsGrid: {
    flexDirection: "row",

    flexWrap: "wrap",

    justifyContent: "space-between",

    marginBottom: 24,
  },

  heroSpacing: {
    marginBottom: 24,
  },

  cardSpacing: {
    marginBottom: 22,
  },

  row: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",
  },

  sectionHeader: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    marginBottom: 18,
  },

  sectionTitle: {
    fontSize: 22,

    fontWeight: "800",

    color: "#0F172A",
  },

  sectionSubtitle: {
    marginTop: 6,

    fontSize: 13,

    color: "#64748B",

    fontWeight: "500",
  },

  viewAll: {
    color: THEME.colors.primary,

    fontSize: 14,

    fontWeight: "700",
  },

  dashboardCard: {
    backgroundColor: "#FFFFFF",

    borderRadius: 24,

    padding: 20,

    borderWidth: 1,

    borderColor: "#E8EDF5",

    shadowColor: "#000",

    shadowOpacity: 0.05,

    shadowRadius: 12,

    shadowOffset: {
      width: 0,
      height: 6,
    },

    elevation: 4,
  },
    statsCard: {
    width: "48%",
    marginBottom: 16,
  },

  quickActionSpacing: {
    marginTop: 8,
    marginBottom: 28,
  },

  analyticsSpacing: {
    marginBottom: 28,
  },

  announcementSpacing: {
    marginBottom: 28,
  },

  activitySpacing: {
    marginBottom: 28,
  },

  pendingSpacing: {
    marginBottom: 20,
  },

  divider: {
    height: 1,
    backgroundColor: "#E8EDF5",
    marginVertical: 24,
  },

  emptyContainer: {
    backgroundColor: "#FFFFFF",

    borderRadius: 22,

    padding: 24,

    justifyContent: "center",

    alignItems: "center",

    borderWidth: 1,

    borderColor: "#E8EDF5",
  },

  emptyText: {
    marginTop: 12,

    fontSize: 15,

    color: "#64748B",

    fontWeight: "600",
  },

  bottomSpacing: {
    height: 120,
  },

});