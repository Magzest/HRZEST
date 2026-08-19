import React from "react";
import {
  ScrollView,
  StyleSheet,
  SafeAreaView,
} from "react-native";

import ProfileHeader from "../../components/profile/ProfileHeader";
import EmptyState from "../../components/ui/EmptyState";

// No Bearer-token-compatible endpoint exists to list, upload, or download
// employee documents from mobile -- every document route in
// blueprints/documents.py is a session-based web route. This screen used
// to show two fabricated "Verified" documents (a fake Aadhaar and PAN
// entry) that could never be cleared, plus an upload flow that always
// claimed success even though the upload call 404'd. Replaced with an
// honest unavailable state.
export default function DocumentsScreen() {
  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader title="Documents & Statutory Files" showBack />

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <EmptyState
          icon="document-text-outline"
          title="Documents aren't on mobile yet"
          description="Uploading and viewing your compliance documents (ID, PAN, certificates) is only available from the web employee portal for now."
        />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F8FAFC" },
  content: { paddingHorizontal: 18, paddingBottom: 120, paddingTop: 18 },
});
