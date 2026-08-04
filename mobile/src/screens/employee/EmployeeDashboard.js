import React, { useState, useCallback } from "react";
import {
  ScrollView,
  StyleSheet,
  RefreshControl,
  Alert,
  View,
  Text,
  TouchableOpacity,
} from "react-native";

import { LinearGradient } from "expo-linear-gradient";
import { useFocusEffect } from "@react-navigation/native";
import { DrawerActions } from "@react-navigation/native";
import {
  fetchEmployeePortal,
  employeeCheckin,
  employeeLogout,
  syncOfflinePunches,
  getPhotoUrl,
  fetchEmployeeAttendance,
  fetchEmployeeLeaves,
} from "../../api/client";
import { queuePunch, getPendingPunches, clearQueue } from "../../utils/offlineQueue";

import { useAuth } from "../../store/AuthContext";

import { Ionicons } from "@expo/vector-icons";
import LoadingSkeleton from "../../components/ui/LoadingSkeleton";
import EmptyState from "../../components/ui/EmptyState";
import AttendanceScannerModal from "../AttendanceScannerModal";

import EmployeeHeroCard from "../../components/employee/EmployeeHeroCard";
import EmployeeAttendanceCard from "../../components/employee/EmployeeAttendanceCard";
import EmployeeSummaryCards from "../../components/employee/EmployeeSummaryCards";
import EmployeeQuickActions from "../../components/employee/EmployeeQuickActions";
import EmployeeRecentAttendance from "../../components/employee/EmployeeRecentAttendance";
import EmployeeAnnouncementCard from "../../components/employee/EmployeeAnnouncementCard";
import EmployeeUpcomingEvents from "../../components/employee/EmployeeUpcomingEvents";
import AiHelpdeskModal from "../../components/common/AiHelpdeskModal";
import DigitalIdCardModal from "../../components/employee/DigitalIdCardModal";

export default function EmployeeDashboard({ navigation }) {

  const { user, signOut } = useAuth();

  const [loading, setLoading]         = useState(true);
  const [refreshing, setRefreshing]   = useState(false);
  const [checking, setChecking]       = useState(false);
  const [data, setData]               = useState(null);
  const [metrics, setMetrics]         = useState({ hours: "0h 00m", attendance: "0%", leaveBalance: "0", performance: "N/A" });
  const [showScanner, setShowScanner] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [syncing, setSyncing]         = useState(false);
  const [showAiModal, setShowAiModal] = useState(false);
  const [showIdCardModal, setShowIdCardModal] = useState(false);

  const loadDashboard = async () => {
    try {
      const portalRes = await fetchEmployeePortal();
      if (portalRes.data.ok) setData(portalRes.data);

      const now = new Date();
      const [attRes, leaveRes] = await Promise.all([
        fetchEmployeeAttendance(now.getFullYear(), now.getMonth() + 1),
        fetchEmployeeLeaves()
      ]);

      let calculatedAttendance = "0%";
      let performanceGrade = "N/A";
      if (attRes.data?.ok && attRes.data?.salary) {
        const { billable, full_days, half_days } = attRes.data.salary;
        const present = full_days + (half_days * 0.5);
        const pct = billable > 0 ? Math.round((present / billable) * 100) : 0;
        calculatedAttendance = `${pct}%`;
        if (pct >= 95) performanceGrade = "A+";
        else if (pct >= 90) performanceGrade = "A";
        else if (pct >= 80) performanceGrade = "B";
        else if (pct >= 70) performanceGrade = "C";
        else performanceGrade = "D";
      }

      let calculatedLeave = "0";
      if (leaveRes.data?.ok && leaveRes.data?.summary) {
        const approved = leaveRes.data.summary.approved || 0;
        const standardQuota = 20;
        calculatedLeave = Math.max(0, standardQuota - approved).toString().padStart(2, '0');
      }

      let calculatedHours = "0h 00m";
      if (portalRes.data?.today_attendance?.login_time) {
        const loginStr = portalRes.data.today_attendance.login_time; // "HH:MM:SS"
        const logoutStr = portalRes.data.today_attendance.logout_time;
        
        const loginParts = loginStr.split(':');
        const loginDt = new Date();
        loginDt.setHours(parseInt(loginParts[0], 10), parseInt(loginParts[1], 10), parseInt(loginParts[2] || 0, 10));

        let logoutDt = new Date(); // current time if not logged out
        if (logoutStr) {
          const outParts = logoutStr.split(':');
          logoutDt = new Date();
          logoutDt.setHours(parseInt(outParts[0], 10), parseInt(outParts[1], 10), parseInt(outParts[2] || 0, 10));
        }
        
        const diffMs = Math.max(0, logoutDt - loginDt);
        const hrs = Math.floor(diffMs / (1000 * 60 * 60));
        const mins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
        calculatedHours = `${hrs.toString().padStart(2, '0')}h ${mins.toString().padStart(2, '0')}m`;
      }

      setMetrics({
        hours: calculatedHours,
        attendance: calculatedAttendance,
        leaveBalance: calculatedLeave,
        performance: performanceGrade
      });

    } catch {
      Alert.alert("Error", "Unable to load some dashboard data.");
    }
    setLoading(false);
    setRefreshing(false);
  };

  const syncPending = async () => {
    const punches = await getPendingPunches();
    if (punches.length === 0) return;
    setSyncing(true);
    try {
      const res = await syncOfflinePunches(punches);
      if (res.data.ok) {
        await clearQueue();
        setPendingCount(0);
        const synced  = res.data.results?.filter(r => r.ok).length ?? punches.length;
        const failed  = res.data.results?.filter(r => !r.ok).length ?? 0;
        const msg     = failed > 0
          ? `${synced} punch(es) synced. ${failed} rejected (too old or duplicate).`
          : `${synced} offline punch(es) synced successfully.`;
        Alert.alert("Sync Complete", msg);
        await loadDashboard();
      }
    } catch {
      // Server still unreachable — keep punches in queue
    }
    setSyncing(false);
  };

  useFocusEffect(
    useCallback(() => {
      getPendingPunches().then(q => setPendingCount(q.length));
      syncPending().then(() => loadDashboard());
    }, [])
  );

  const handleCheckIn = async () => {
    setChecking(true);
    try {
      const res = await employeeCheckin();
      if (res.data.ok) {
        Alert.alert(
          res.data.action === "login" ? "Checked In" : "Checked Out",
          `${res.data.status}\n${res.data.time}`
        );
        await loadDashboard();
      } else {
        Alert.alert("Unable", res.data.msg);
      }
    } catch (e) {
      const isNetworkError = !e.response;
      if (isNetworkError) {
        await queuePunch();
        const q = await getPendingPunches();
        setPendingCount(q.length);
        Alert.alert(
          "Saved Offline",
          "No internet connection. Your punch has been saved and will sync automatically when you're back online."
        );
      } else {
        Alert.alert("Error", e.response?.data?.msg || "Something went wrong.");
      }
    }
    setChecking(false);
  };

  const handleLogout = async () => {
    try {
      await employeeLogout();
    } catch {}
    signOut();
  };

  const attendance = data?.today_attendance;
  const photoUrl   = data?.employee_id ? getPhotoUrl(data.employee_id) : null;

  if (loading) {
    return (
      <LinearGradient
        colors={["#F8FAFC", "#F3F7FD", "#EDF4FF"]}
        style={styles.loadingContainer}
      >
        <LoadingSkeleton />
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
      <AttendanceScannerModal
        visible={showScanner}
        onClose={() => setShowScanner(false)}
        onSuccess={() => loadDashboard()}
      />

      {pendingCount > 0 && (
        <View style={styles.syncBanner}>
          <Text style={styles.syncBannerText}>
            {syncing
              ? "⏳ Syncing offline punches…"
              : `📶 ${pendingCount} offline punch${pendingCount > 1 ? "es" : ""} pending sync`}
          </Text>
          {!syncing && (
            <Text style={styles.syncBannerLink} onPress={syncPending}>
              Sync now
            </Text>
          )}
        </View>
      )}

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              loadDashboard();
            }}
            colors={["#173B8C"]}
            tintColor="#173B8C"
          />
        }
      >
        <EmployeeHeroCard
          employeeName={data?.name || user?.name}
          designation={data?.role || data?.designation || user?.role}
          employeeId={data?.employee_id || user?.employeeId}
          date={data?.today}
          attendance={attendance}
          checking={checking}
          onCheckIn={handleCheckIn}
          onLogout={handleLogout}
          photoUrl={photoUrl}
          onScanQR={() => setShowScanner(true)}
          onMenu={() => navigation.dispatch(DrawerActions.openDrawer())}
          companyName={data?.company_name || user?.company}
        />
  <EmployeeAttendanceCard attendance={attendance} />

        <EmployeeSummaryCards
          hours={metrics.hours}
          attendance={metrics.attendance}
          leaveBalance={metrics.leaveBalance}
          performance={metrics.performance}
        />

        <EmployeeQuickActions navigation={navigation} />

        {data?.recent_attendance?.length > 0 ? (
          <EmployeeRecentAttendance records={data.recent_attendance} />
        ) : (
          <EmptyState
            icon="calendar-outline"
            title="No Recent Attendance"
            subtitle="Your attendance history will appear here."
          />
        )}

        <EmployeeAnnouncementCard announcements={data?.announcements || []} />

        <EmployeeUpcomingEvents events={data?.upcoming_events || []} />

        <View style={styles.bottomSpacing} />

      </ScrollView>

      {/* Floating Action Button for AI HRMS Helpdesk */}
      <TouchableOpacity
        activeOpacity={0.88}
        style={{
          position: "absolute",
          right: 20,
          bottom: 75,
          backgroundColor: "#173B8C",
          width: 56,
          height: 56,
          borderRadius: 28,
          justifyContent: "center",
          alignItems: "center",
          elevation: 8,
          shadowColor: "#173B8C",
          shadowOpacity: 0.4,
          shadowRadius: 10,
          shadowOffset: { width: 0, height: 4 },
        }}
        onPress={() => setShowAiModal(true)}
      >
        <Ionicons name="sparkles" size={24} color="#FFFFFF" />
      </TouchableOpacity>

      <AiHelpdeskModal visible={showAiModal} onClose={() => setShowAiModal(false)} />
      <DigitalIdCardModal visible={showIdCardModal} employee={data} onClose={() => setShowIdCardModal(false)} />
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#F8FAFC",
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: 55,
    paddingBottom: 120,
  },
  bottomSpacing: {
    height: 30,
  },
  syncBanner: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "#FEF3C7",
    borderBottomWidth: 1,
    borderBottomColor: "#FDE68A",
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  syncBannerText: {
    fontSize: 13,
    color: "#92400E",
    fontWeight: "500",
    flex: 1,
  },
  syncBannerLink: {
    fontSize: 13,
    color: "#1D4ED8",
    fontWeight: "700",
    marginLeft: 12,
  },
});
