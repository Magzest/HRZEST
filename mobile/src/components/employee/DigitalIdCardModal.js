import React from "react";
import { Modal, View, Text, StyleSheet, TouchableOpacity, Image } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";

import { API_BASE_URL } from "../../config";

import { useAuth } from "../../store/AuthContext";

export default function DigitalIdCardModal({ visible, employee, onClose }) {
  const { user } = useAuth();
  if (!employee) return null;

  const companyName = (employee.company || user?.company || "Enterprise Workforce Platform").toUpperCase();
  const empId = employee.employeeId || employee.employee_id || "EMP-1001";
  const serverQrUri = `${API_BASE_URL}/static/qrcodes/${empId}.png`;
  const fallbackQrUri = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(empId)}`;
  const [qrUri, setQrUri] = React.useState(serverQrUri);

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.cardContainer}>
          <LinearGradient colors={["#0F2027", "#203A43", "#2C5364"]} style={styles.cardHeader}>
            <View style={styles.headerRow}>
              <Ionicons name="business" size={22} color="#38BDF8" />
              <Text style={styles.companyName}>{companyName}</Text>
            </View>
            <Text style={styles.cardSubtitle}>OFFICIAL IDENTIFICATION CARD</Text>
          </LinearGradient>

          <View style={styles.cardBody}>
            <View style={styles.avatarBorder}>
              {employee.photo ? (
                <Image source={{ uri: employee.photo }} style={styles.avatarImage} />
              ) : (
                <View style={styles.avatarFallback}>
                  <Text style={styles.avatarText}>{employee.name ? employee.name.charAt(0) : "E"}</Text>
                </View>
              )}
            </View>

            <Text style={styles.empName}>{employee.name || "Employee Name"}</Text>
            <Text style={styles.empRole}>{employee.role || "Software Engineer"}</Text>
            <View style={styles.badgeRow}>
              <View style={styles.deptBadge}>
                <Text style={styles.deptBadgeText}>{employee.department || "Engineering"}</Text>
              </View>
            </View>

            <View style={styles.detailsTable}>
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>EMP ID:</Text>
                <Text style={styles.detailValue}>{empId}</Text>
              </View>
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>STATUS:</Text>
                <Text style={[styles.detailValue, { color: "#10B981" }]}>Active Staff</Text>
              </View>
            </View>

            <View style={styles.qrContainer}>
              <Image
                source={{ uri: qrUri }}
                style={{ width: 120, height: 120, borderRadius: 12 }}
                onError={() => setQrUri(fallbackQrUri)}
              />
              <Text style={styles.qrText}>Scan for Digital Verification</Text>
            </View>
          </View>

          <TouchableOpacity style={styles.closeBtn} onPress={onClose}>
            <Text style={styles.closeBtnText}>Close ID Card</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: "rgba(15, 23, 42, 0.8)", justifyContent: "center", alignItems: "center", padding: 20 },
  cardContainer: { width: "90%", backgroundColor: "#FFFFFF", borderRadius: 24, overflow: "hidden", elevation: 12 },
  cardHeader: { paddingVertical: 18, paddingHorizontal: 20, alignItems: "center" },
  headerRow: { flexDirection: "row", alignItems: "center" },
  companyName: { fontSize: 15, fontWeight: "800", color: "#FFFFFF", marginLeft: 8, letterSpacing: 0.5 },
  cardSubtitle: { fontSize: 10, fontWeight: "700", color: "#94A3B8", letterSpacing: 1.2, marginTop: 4 },
  cardBody: { alignItems: "center", padding: 20 },
  avatarBorder: { width: 90, height: 90, borderRadius: 45, borderWidth: 3, borderColor: "#38BDF8", justifyContent: "center", alignItems: "center", marginTop: -40, backgroundColor: "#FFFFFF", elevation: 4 },
  avatarImage: { width: 84, height: 84, borderRadius: 42 },
  avatarFallback: { width: 84, height: 84, borderRadius: 42, backgroundColor: "#173B8C", justifyContent: "center", alignItems: "center" },
  avatarText: { fontSize: 24, fontWeight: "800", color: "#FFFFFF" },
  empName: { fontSize: 16, fontWeight: "800", color: "#0F172A", marginTop: 10 },
  empRole: { fontSize: 12, fontWeight: "600", color: "#64748B", marginTop: 2 },
  badgeRow: { marginTop: 8 },
  deptBadge: { backgroundColor: "#E0F2FE", paddingHorizontal: 12, paddingVertical: 4, borderRadius: 12 },
  deptBadgeText: { fontSize: 11, fontWeight: "700", color: "#0369A1" },
  detailsTable: { width: "100%", marginTop: 16, borderTopWidth: 1, borderTopColor: "#F1F5F9", paddingTop: 12 },
  detailRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: 6 },
  detailLabel: { fontSize: 12, fontWeight: "700", color: "#64748B" },
  detailValue: { fontSize: 12, fontWeight: "700", color: "#0F172A" },
  qrContainer: { alignItems: "center", marginTop: 14, paddingTop: 12, borderTopWidth: 1, borderTopColor: "#F1F5F9", width: "100%" },
  qrText: { fontSize: 11, color: "#94A3B8", marginTop: 4 },
  closeBtn: { backgroundColor: "#F1F5F9", paddingVertical: 14, alignItems: "center" },
  closeBtnText: { color: "#64748B", fontWeight: "700", fontSize: 13 },
});
