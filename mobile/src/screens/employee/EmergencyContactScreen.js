import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  SafeAreaView,
  ActivityIndicator,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../store/AuthContext";
import { fetchEmployeeProfile } from "../../api/client";
import ProfileHeader from "../../components/profile/ProfileHeader";
import DetailCard from "../../components/profile/DetailCard";

export default function EmergencyContactScreen() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [emergency, setEmergency] = useState({
    primaryName: user?.emergency_contact_name || "Family Contact",
    primaryRelation: user?.emergency_contact_relation || "Parent / Guardian",
    primaryPhone: user?.emergency_contact_phone || "Not Specified",
    address: user?.address || "Registered Family Address",
  });

  useEffect(() => {
    fetchEmployeeProfile()
      .then((res) => {
        if (res?.data?.ok && res?.data?.profile) {
          const p = res.data.profile;
          setEmergency({
            primaryName: p.emergency_contact_name || user?.emergency_contact_name || "Family Contact",
            primaryRelation: p.emergency_contact_relation || user?.emergency_contact_relation || "Parent / Guardian",
            primaryPhone: p.emergency_contact_phone || user?.emergency_contact_phone || "Not Specified",
            address: p.address || user?.address || "Registered Family Address",
          });
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader title="Emergency Contact" showBack />

      {loading ? (
        <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
          <ActivityIndicator size="large" color="#173B8C" />
        </View>
      ) : (
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
          {/* Summary Card */}
          <View style={styles.summaryCard}>
            <View style={styles.avatar}>
              <Ionicons name="medical" size={24} color="#FFFFFF" />
            </View>

            <View style={styles.summaryText}>
              <Text style={styles.name}>{emergency.primaryName}</Text>
              <Text style={styles.subText}>{emergency.primaryRelation} • {emergency.primaryPhone}</Text>
            </View>
          </View>

          {/* Details */}
          <DetailCard icon="person-outline" label="Contact Name" value={emergency.primaryName} />
          <DetailCard icon="people-outline" label="Relationship" value={emergency.primaryRelation} />
          <DetailCard icon="call-outline" label="Phone Number" value={emergency.primaryPhone} />
          <DetailCard icon="location-outline" label="Family Address" value={emergency.address} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F8FAFC" },
  content: { padding: 18, paddingBottom: 40 },
  summaryCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#EF4444",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 14,
  },
  summaryText: { flex: 1 },
  name: { fontSize: 16, fontWeight: "800", color: "#0F172A" },
  subText: { fontSize: 13, fontWeight: "600", color: "#64748B", marginTop: 2 },
});