import React from "react";
import {
  ScrollView,
  StyleSheet,
  SafeAreaView,
} from "react-native";

import ProfileHeader from "../../components/profile/ProfileHeader";
import EmptyState from "../../components/ui/EmptyState";

// No Bearer-token-compatible endpoint exists to read or write education
// records from mobile (add_education_entry / delete_education_entry are
// session-based web routes only). This used to show a fabricated seeded
// qualification and let you "add" more that vanished on app close --
// replaced with an honest unavailable state instead.
export default function EducationScreen() {
  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader title="Education" showBack />

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <EmptyState
          icon="school-outline"
          title="Education records aren't on mobile yet"
          description="Adding and viewing your academic qualifications is only available from the web employee portal for now."
        />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F8FAFC" },
  content: { paddingHorizontal: 18, paddingBottom: 120, paddingTop: 18 },
});
