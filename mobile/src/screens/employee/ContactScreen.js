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

export default function ContactScreen() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [contactInfo, setContactInfo] = useState({
    workEmail: user?.email || `${user?.employeeId || "emp"}@company.com`,
    phone: user?.phone || "Not Provided",
    address: user?.address || "Corporate HQ Address",
    city: user?.city || "Hyderabad",
    state: user?.state || "Telangana",
    pincode: user?.pincode || "500081",
    country: "India",
    emergencyContact: user?.emergency_contact_name || "Family Contact",
    emergencyPhone: user?.emergency_contact_phone || "Not Provided",
  });

  useEffect(() => {
    fetchEmployeeProfile()
      .then((res) => {
        if (res?.data?.ok && res?.data?.profile) {
          const p = res.data.profile;
          setContactInfo({
            workEmail: p.email || user?.email || `${p.employee_id}@company.com`,
            phone: p.phone || "Not Provided",
            address: p.address || "Corporate HQ Address",
            city: p.city || "Hyderabad",
            state: p.state || "Telangana",
            pincode: p.pincode || "500081",
            country: "India",
            emergencyContact: p.emergency_contact_name || "Family Contact",
            emergencyPhone: p.emergency_contact_phone || "Not Provided",
          });
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader title="Contact Information" showBack />

      {loading ? (
        <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
          <ActivityIndicator size="large" color="#173B8C" />
        </View>
      ) : (
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
          {/* Summary Card */}
          <View style={styles.summaryCard}>
            <View style={styles.avatar}>
              <Ionicons name="call" size={24} color="#FFFFFF" />
            </View>

            <View style={styles.summaryText}>
              <Text style={styles.name}>{contactInfo.workEmail}</Text>
              <Text style={styles.subText}>{contactInfo.phone}</Text>
            </View>
          </View>

          {/* Details */}
          <DetailCard icon="mail-outline" label="Work Email" value={contactInfo.workEmail} />
          <DetailCard icon="call-outline" label="Phone Number" value={contactInfo.phone} />
          <DetailCard icon="location-outline" label="Residential Address" value={contactInfo.address} />
          <DetailCard icon="business-outline" label="City & State" value={`${contactInfo.city}, ${contactInfo.state}`} />
          <DetailCard icon="map-outline" label="Pincode" value={contactInfo.pincode} />
          <DetailCard icon="people-outline" label="Emergency Contact" value={`${contactInfo.emergencyContact} (${contactInfo.emergencyPhone})`} />
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
    backgroundColor: "#173B8C",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 14,
  },
  summaryText: { flex: 1 },
  name: { fontSize: 15, fontWeight: "800", color: "#0F172A" },
  subText: { fontSize: 13, fontWeight: "600", color: "#64748B", marginTop: 2 },
});