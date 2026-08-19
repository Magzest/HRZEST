import React, { useState, useCallback } from "react";
import {
  SafeAreaView,
  ScrollView,
  RefreshControl,
} from "react-native";

import { StyleSheet } from "react-native";
import { useFocusEffect } from "@react-navigation/native";

import ProfileHeader from "../../components/profile/ProfileHeader";
import EmptyState from "../../components/ui/EmptyState";
import LoadingSkeleton from "../../components/ui/LoadingSkeleton";

import EmployeePerformanceCard from "../../components/performance/EmployeePerformanceCard";

import { useAuth } from "../../store/AuthContext";
import { fetchEmployeeProfile } from "../../api/client";

export default function PerformanceScreen() {
  const { user } = useAuth();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetchEmployeeProfile();
      if (res?.data?.ok) setProfile(res.data.profile);
    } catch (_) {
      // Fall back to whatever identity AuthContext already has.
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      (async () => {
        setLoading(true);
        if (!cancelled) await load();
        if (!cancelled) setLoading(false);
      })();
      return () => { cancelled = true; };
    }, [load])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const name = profile?.name || user?.name || "Employee";
  const employeeId = profile?.employee_id || user?.employeeId || "-";
  const designation = profile?.role || "-";
  const department = profile?.department || "-";

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader
        title="My Performance"
        showBack={false}
      />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {loading ? (
          <>
            <LoadingSkeleton height={110} radius={24} style={{ marginBottom: 22 }} />
            <LoadingSkeleton height={140} radius={24} />
          </>
        ) : (
          <>
            <EmployeePerformanceCard
              name={name}
              designation={designation}
              department={department}
              employeeId={employeeId}
            />

            <EmptyState
              icon="stats-chart-outline"
              title="Performance reviews aren't available on mobile yet"
              description="Your quarterly ratings, KPIs and manager feedback are managed on the web portal for now. Ask your manager or HR admin for your latest review, or check the web dashboard."
            />
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F8FAFC",
  },

  content: {
    paddingHorizontal: 18,
    paddingBottom: 120,
    paddingTop: 18,
  },
});
