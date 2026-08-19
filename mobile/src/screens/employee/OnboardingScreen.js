import React, { useState, useCallback } from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";

import ProfileHeader from "../../components/profile/ProfileHeader";
import EmptyState from "../../components/ui/EmptyState";
import LoadingSkeleton from "../../components/ui/LoadingSkeleton";

import OnboardingStatusCard from "../../components/onboarding/OnboardingStatusCard";

import { useAuth } from "../../store/AuthContext";
import { fetchEmployeeProfile } from "../../api/client";

// No Bearer-token-compatible endpoint exposes an employee's own onboarding
// progress/checklist/timeline (only a session-based web route, /my_onboarding,
// does) -- so this screen shows the real employee identity and an honest
// "not available" state instead of the fully hardcoded "John Doe / 72% /
// Priya Sharma" content it used to have.
export default function OnboardingScreen() {
  const { user } = useAuth();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      (async () => {
        setLoading(true);
        try {
          const res = await fetchEmployeeProfile();
          if (!cancelled && res?.data?.ok) setProfile(res.data.profile);
        } catch (_) {}
        if (!cancelled) setLoading(false);
      })();
      return () => { cancelled = true; };
    }, [])
  );

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader
        title="My Onboarding"
        showBack={false}
      />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
      >
        {loading ? (
          <LoadingSkeleton height={110} radius={24} />
        ) : (
          <>
            <OnboardingStatusCard
              employeeName={profile?.name || user?.name || "Employee"}
              employeeId={profile?.employee_id || user?.employeeId || "-"}
              status="Active"
            />

            <EmptyState
              icon="checkmark-done-circle-outline"
              title="Onboarding tracker isn't on mobile yet"
              description="Your onboarding checklist, timeline and HR contact are managed on the web portal for now. Check there for your current progress."
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
