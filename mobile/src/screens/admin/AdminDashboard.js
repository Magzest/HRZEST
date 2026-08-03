import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  SafeAreaView,
  TouchableOpacity,
  Modal,
  FlatList,
} from "react-native";

import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";

import AdminHeader from "../../components/admin/AdminHeader";
import AdminSearchBar from "../../components/admin/AdminSearchBar";
import DashboardHeroCard from "../../components/admin/DashboardHeroCard";
import AttendanceOverviewCard from "../../components/admin/AttendanceOverviewCard";
import QuickActionGrid from "../../components/admin/QuickActionGrid";
import PendingApprovalCard from "../../components/admin/PendingApprovalCard";
import AnalyticsOverviewCard from "../../components/admin/AnalyticsOverviewCard";
import AnnouncementCard from "../../components/admin/AnnouncementCard";
import RecentActivityList from "../../components/admin/RecentActivityList";

import { fetchDashboard } from "../../api/client";

const ALL_ANNOUNCEMENTS = [
  {
    id: "1",
    title: "Company Quarterly All-Hands Meeting",
    message:
      "Monthly all-hands meeting scheduled for tomorrow at 10:00 AM in Conference Room A & Zoom link.",
    date: "Tomorrow, 10:00 AM",
    category: "Meeting",
    icon: "people",
    color: "#16A34A",
    bg: "#DCFCE7",
  },
  {
    id: "2",
    title: "Independence Day Public Holiday Notice",
    message:
      "Office will remain closed on 15th August for Independence Day. Emergency support remains on standby.",
    date: "15 Aug 2026",
    category: "Holiday",
    icon: "airplane",
    color: "#0B2253",
    bg: "#EFF6FF",
  },
  {
    id: "3",
    title: "Monthly Salary Disbursement Status",
    message:
      "Payroll for current month has been processed. Salary slips are available for download under Payslips & Earnings.",
    date: "End of Month",
    category: "Payroll",
    icon: "wallet",
    color: "#7C3AED",
    bg: "#EDE9FE",
  },
  {
    id: "4",
    title: "Updated Office Health & Security Policy",
    message:
      "All staff members must scan individual QR codes or geofence check-in upon entering company premises.",
    date: "Active Policy",
    category: "Policy",
    icon: "shield-checkmark",
    color: "#F59E0B",
    bg: "#FEF3C7",
  },
];

export default function AdminDashboard({ navigation }) {
  const [search, setSearch] = useState("");
  const [dashboardData, setDashboardData] = useState(null);
  const [announcementModalVisible, setAnnouncementModalVisible] = useState(false);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const res = await fetchDashboard();
      if (res?.data) {
        setDashboardData(res.data);
      }
    } catch (_) {}
  };

  return (
    <LinearGradient colors={["#F8FAFC", "#F1F5F9"]} style={styles.container}>
      <SafeAreaView style={styles.container}>
        <AdminHeader title="Admin Dashboard" navigation={navigation} />

        <ScrollView
          style={styles.container}
          contentContainerStyle={styles.content}
          showsVerticalScrollIndicator={false}
        >
          <DashboardHeroCard
            present={dashboardData?.present || 228}
            total={dashboardData?.total_employees || 252}
          />

          <AdminSearchBar
            value={search}
            onChangeText={setSearch}
            placeholder="Search employees or features..."
            onFilterPress={() => navigation.navigate("Employees")}
            onClear={() => setSearch("")}
          />

          <View style={styles.sectionSpacing} />

          <AttendanceOverviewCard
            present={dashboardData?.present || 228}
            absent={dashboardData?.absent || 18}
            late={dashboardData?.late || 8}
            onLeave={dashboardData?.onLeave || 6}
            navigation={navigation}
          />

          <QuickActionGrid navigation={navigation} />

          {/* Pending Leave Approval Card */}
          <PendingApprovalCard
            title="Leave Requests"
            pending={8}
            subtitle="Requires your approval"
            icon="document-text-outline"
            color="#F59E0B"
            background="#FEF3C7"
            onPress={() => navigation.navigate("LeaveRequests")}
          />

          {/* Pending Payroll Approval Card */}
          <PendingApprovalCard
            title="Payroll Approval"
            pending={3}
            subtitle="Waiting for verification"
            icon="wallet-outline"
            color="#7C3AED"
            background="#EDE9FE"
            onPress={() => navigation.navigate("Payroll")}
          />

          <AnalyticsOverviewCard navigation={navigation} />

          {/* Announcements Card with Working View All */}
          <AnnouncementCard
            onViewAll={() => setAnnouncementModalVisible(true)}
          />

          <RecentActivityList />

          <View style={styles.bottomSpacing} />
        </ScrollView>

        {/* Announcements Modal */}
        <Modal
          visible={announcementModalVisible}
          animationType="slide"
          transparent={true}
          onRequestClose={() => setAnnouncementModalVisible(false)}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <View style={styles.modalHeader}>
                <View style={{ flexDirection: "row", alignItems: "center" }}>
                  <Ionicons name="megaphone" size={22} color="#0B2253" />
                  <Text style={styles.modalTitle}>Company Announcements</Text>
                </View>
                <TouchableOpacity
                  style={styles.closeBtn}
                  onPress={() => setAnnouncementModalVisible(false)}
                >
                  <Ionicons name="close" size={20} color="#0F172A" />
                </TouchableOpacity>
              </View>

              <FlatList
                data={ALL_ANNOUNCEMENTS}
                keyExtractor={(item) => item.id}
                showsVerticalScrollIndicator={false}
                renderItem={({ item }) => (
                  <View style={styles.announcementItem}>
                    <View style={[styles.itemIconBox, { backgroundColor: item.bg }]}>
                      <Ionicons name={item.icon} size={22} color={item.color} />
                    </View>
                    <View style={{ flex: 1, marginLeft: 14 }}>
                      <View style={styles.itemMetaRow}>
                        <Text style={styles.itemTitle}>{item.title}</Text>
                        <View style={[styles.categoryBadge, { backgroundColor: item.bg }]}>
                          <Text style={[styles.categoryText, { color: item.color }]}>
                            {item.category}
                          </Text>
                        </View>
                      </View>
                      <Text style={styles.itemMsg}>{item.message}</Text>
                      <Text style={styles.itemDate}>📅 {item.date}</Text>
                    </View>
                  </View>
                )}
              />
            </View>
          </View>
        </Modal>
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
    height: 16,
  },
  bottomSpacing: {
    height: 40,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.5)",
    justifyContent: "flex-end",
  },
  modalContent: {
    backgroundColor: "#FFFFFF",
    borderTopLeftRadius: 26,
    borderTopRightRadius: 26,
    maxHeight: "82%",
    padding: 20,
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 18,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#E2E8F0",
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: "#0F172A",
    marginLeft: 10,
  },
  closeBtn: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: "#F1F5F9",
    justifyContent: "center",
    alignItems: "center",
  },
  announcementItem: {
    flexDirection: "row",
    backgroundColor: "#F8FAFC",
    borderRadius: 18,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  itemIconBox: {
    width: 44,
    height: 44,
    borderRadius: 14,
    justifyContent: "center",
    alignItems: "center",
  },
  itemMetaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  itemTitle: {
    flex: 1,
    fontSize: 15,
    fontWeight: "700",
    color: "#0F172A",
    marginRight: 6,
  },
  categoryBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
  },
  categoryText: {
    fontSize: 10,
    fontWeight: "800",
  },
  itemMsg: {
    marginTop: 6,
    fontSize: 13,
    color: "#475569",
    lineHeight: 18,
  },
  itemDate: {
    marginTop: 8,
    fontSize: 11,
    color: "#94A3B8",
    fontWeight: "600",
  },
});