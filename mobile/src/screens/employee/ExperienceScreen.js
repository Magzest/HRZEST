import React from "react";
import {
  ScrollView,
  StyleSheet,
  SafeAreaView,
} from "react-native";

import ProfileHeader from "../../components/profile/ProfileHeader";
import EmptyState from "../../components/ui/EmptyState";

// No Bearer-token-compatible endpoint exists to read or write work
// experience records from mobile (add_experience / delete_experience are
// session-based web routes only). This used to show a fabricated seeded
// entry ("Software Engineer @ Acme Tech Solutions") and let you "add" more
// that vanished on app close -- replaced with an honest unavailable state.
export default function ExperienceScreen() {
  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader title="Experience" showBack />

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <EmptyState
          icon="layers-outline"
          title="Experience records aren't on mobile yet"
          description="Adding and viewing your previous employment history is only available from the web employee portal for now."
        />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F8FAFC" },
  content: { paddingHorizontal: 18, paddingBottom: 120, paddingTop: 18 },
});
