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

export default function BankDetailsScreen() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [bankInfo, setBankInfo] = useState({
    accountName: user?.name || "",
    bankName: user?.bank_name || "Not Provided",
    accountNumber: user?.bank_account || "Not Provided",
    ifscCode: user?.bank_ifsc || "Not Provided",
    panNumber: user?.pan_number || "Not Provided",
    aadharNumber: user?.aadhar_number || "Not Provided",
  });

  useEffect(() => {
    fetchEmployeeProfile()
      .then((res) => {
        if (res?.data?.ok && res?.data?.profile) {
          const p = res.data.profile;
          setBankInfo({
            accountName: p.name || user?.name || "",
            bankName: p.bank_name || user?.bank_name || "Not Provided",
            accountNumber: p.bank_account || user?.bank_account || "Not Provided",
            ifscCode: p.bank_ifsc || user?.bank_ifsc || "Not Provided",
            panNumber: p.pan_number || user?.pan_number || "Not Provided",
            aadharNumber: p.aadhar_number || user?.aadhar_number || "Not Provided",
          });
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader title="Bank Details" showBack />

      {loading ? (
        <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
          <ActivityIndicator size="large" color="#173B8C" />
        </View>
      ) : (
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
          {/* Summary Card */}
          <View style={styles.summaryCard}>
            <View style={styles.avatar}>
              <Ionicons name="card" size={24} color="#FFFFFF" />
            </View>

            <View style={styles.summaryText}>
              <Text style={styles.name}>{bankInfo.bankName}</Text>
              <Text style={styles.subText}>{bankInfo.accountName}</Text>
            </View>
          </View>

          {/* Details */}
          <DetailCard icon="business-outline" label="Bank Name" value={bankInfo.bankName} />
          <DetailCard icon="person-outline" label="Account Holder" value={bankInfo.accountName} />
          <DetailCard icon="card-outline" label="Account Number" value={bankInfo.accountNumber} />
          <DetailCard icon="qr-code-outline" label="IFSC Code" value={bankInfo.ifscCode} />
          <DetailCard icon="document-text-outline" label="PAN Number" value={bankInfo.panNumber} />
          <DetailCard icon="id-card-outline" label="Aadhar Number" value={bankInfo.aadharNumber} />
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
    backgroundColor: "#16A34A",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 14,
  },
  summaryText: { flex: 1 },
  name: { fontSize: 16, fontWeight: "800", color: "#0F172A" },
  subText: { fontSize: 13, fontWeight: "600", color: "#64748B", marginTop: 2 },
});