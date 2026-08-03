import React from "react";

import {
  Modal,
  View,
 Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Pressable,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import SALARY_THEME from "../../../constants/salaryTheme";

export default function EmployeeSalaryBottomSheet({
  visible,
  employee,
  onClose,
  onDownload,
  onEmail,
  onPrint,
}) {
  if (!employee) return null;

  const Row = ({ label, value, valueColor }) => (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>
        {label}
      </Text>

      <Text
        style={[
          styles.rowValue,
          valueColor && {
            color: valueColor,
          },
        ]}
      >
        {value}
      </Text>
    </View>
  );

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <Pressable
        style={styles.overlay}
        onPress={onClose}
      />

      <View style={styles.sheet}>

        <View style={styles.handle} />

        <ScrollView
          showsVerticalScrollIndicator={false}
        >

          {/* Header */}

          <View style={styles.header}>

            <View style={styles.avatar}>
              <Text style={styles.avatarText}>
                {(employee?.name || "E").charAt(0)}
              </Text>
            </View>

            <Text style={styles.name}>
              {employee?.name || "Employee"}
            </Text>

            <Text style={styles.designation}>
              {employee?.designation || employee?.role || "Staff"}
            </Text>

            <Text style={styles.department}>
              {employee?.department || "Engineering"}
            </Text>
          </View>

          {/* Attendance */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>
              Attendance Summary
            </Text>

            <Row
              label="Working Days"
              value={employee?.workDays ?? 22}
            />

            <Row
              label="Full Days"
              value={employee?.attendance?.full ?? 20}
            />

            <Row
              label="Late Login"
              value={employee?.attendance?.late ?? 2}
            />

            <Row
              label="Half Days"
              value={employee?.attendance?.half ?? 0}
            />

            <Row
              label="Absent"
              value={employee?.attendance?.absent ?? 0}
            />
          </View>

          {/* Earnings */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>
              Earnings
            </Text>

            <Row
              label="Full Day Pay"
              value={`₹ ${employee?.earnings?.fullDayPay ?? (employee?.gross || 85000)}`}
            />

            <Row
              label="Late Pay"
              value={`₹ ${employee?.earnings?.latePay ?? 0}`}
            />

            <Row
              label="Half Day Pay"
              value={`₹ ${employee?.earnings?.halfDayPay ?? 0}`}
            />

            <Row
              label="Incentives"
              value={`₹ ${employee?.earnings?.incentive ?? 0}`}
            />
          </View>

          {/* Deductions */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>
              Deductions
            </Text>

            <Row
              label="Late"
              value={`₹ ${employee?.deductions?.late ?? 0}`}
              valueColor={SALARY_THEME.colors.danger}
            />

            <Row
              label="Half Day"
              value={`₹ ${employee?.deductions?.halfDay ?? 0}`}
              valueColor={SALARY_THEME.colors.danger}
            />

            <Row
              label="Absent"
              value={`₹ ${typeof employee?.deductions === 'number' ? employee.deductions : (employee?.deductions?.absent ?? 0)}`}
              valueColor={SALARY_THEME.colors.danger}
            />
          </View>

          {/* Net Salary */}
          <View style={styles.totalCard}>
            <Text style={styles.totalLabel}>
              Net Salary
            </Text>

            <Text style={styles.totalAmount}>
              ₹ {employee?.netSalary ?? employee?.net ?? 0}
            </Text>
          </View>

          {/* Buttons */}

          <TouchableOpacity
            style={styles.primaryButton}
            onPress={() =>
              onDownload(employee)
            }
          >

            <Ionicons
              name="download-outline"
              size={20}
              color="#FFFFFF"
            />

            <Text
              style={styles.primaryText}
            >
              Download Payslip
            </Text>

          </TouchableOpacity>

          <TouchableOpacity
            style={styles.secondaryButton}
            onPress={() =>
              onEmail(employee)
            }
          >

            <Ionicons
              name="mail-outline"
              size={20}
              color={
                SALARY_THEME.colors.primary
              }
            />

            <Text
              style={styles.secondaryText}
            >
              Email Payslip
            </Text>

          </TouchableOpacity>

          <TouchableOpacity
            style={styles.secondaryButton}
            onPress={() =>
              onPrint(employee)
            }
          >

            <Ionicons
              name="print-outline"
              size={20}
              color={
                SALARY_THEME.colors.primary
              }
            />

            <Text
              style={styles.secondaryText}
            >
              Print Payslip
            </Text>

          </TouchableOpacity>

          <TouchableOpacity
            style={styles.closeButton}
            onPress={onClose}
          >

            <Text style={styles.closeText}>
              Close
            </Text>

          </TouchableOpacity>

        </ScrollView>

      </View>

    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(15,23,42,0.35)",
  },

  sheet: {
    maxHeight: "88%",

    backgroundColor:
      SALARY_THEME.colors.background,

    borderTopLeftRadius: 28,

    borderTopRightRadius: 28,

    padding: 20,
  },

  handle: {
    width: 55,

    height: 5,

    borderRadius: 5,

    alignSelf: "center",

    backgroundColor:
      SALARY_THEME.colors.border,

    marginBottom: 18,
  },

  header: {
    alignItems: "center",

    marginBottom: 24,
  },

  avatar: {
    width: 72,

    height: 72,

    borderRadius: 36,

    backgroundColor:
      SALARY_THEME.colors.primaryLight,

    justifyContent: "center",

    alignItems: "center",
  },

  avatarText: {
    fontSize: 28,

    fontWeight: "800",

    color:
      SALARY_THEME.colors.primary,
  },

  name: {
    marginTop: 14,

    fontSize: 22,

    fontWeight: "800",

    color:
      SALARY_THEME.colors.textPrimary,
  },

  designation: {
    marginTop: 4,

    fontSize: 14,

    color:
      SALARY_THEME.colors.textMuted,
  },

  department: {
    marginTop: 2,

    fontSize: 13,

    color:
      SALARY_THEME.colors.textLight,
  },

  card: {
    backgroundColor:
      SALARY_THEME.colors.surface,

    borderRadius: 18,

    padding: 18,

    marginBottom: 18,

    borderWidth: 1,

    borderColor:
      SALARY_THEME.colors.border,

    ...SALARY_THEME.shadow,
  },

  cardTitle: {
    fontSize: 17,

    fontWeight: "700",

    color:
      SALARY_THEME.colors.textPrimary,

    marginBottom: 14,
  },

  row: {
    flexDirection: "row",

    justifyContent: "space-between",

    marginBottom: 14,
  },

  rowLabel: {
    fontSize: 14,

    color:
      SALARY_THEME.colors.textMuted,
  },

  rowValue: {
    fontSize: 14,

    fontWeight: "700",

    color:
      SALARY_THEME.colors.textPrimary,
  },

  totalCard: {
    backgroundColor:
      SALARY_THEME.colors.primary,

    borderRadius: 18,

    padding: 22,

    alignItems: "center",

    marginBottom: 20,
  },

  totalLabel: {
    color: "#FFFFFF",

    fontSize: 14,
  },

  totalAmount: {
    marginTop: 6,

    color: "#FFFFFF",

    fontSize: 32,

    fontWeight: "800",
  },

  primaryButton: {
    height: 52,

    borderRadius: 14,

    backgroundColor:
      SALARY_THEME.colors.primary,

    justifyContent: "center",

    alignItems: "center",

    flexDirection: "row",

    marginBottom: 12,
  },

  primaryText: {
    marginLeft: 10,

    color: "#FFFFFF",

    fontWeight: "700",

    fontSize: 15,
  },

  secondaryButton: {
    height: 52,

    borderRadius: 14,

    borderWidth: 1,

    borderColor:
      SALARY_THEME.colors.border,

    backgroundColor:
      SALARY_THEME.colors.surface,

    justifyContent: "center",

    alignItems: "center",

    flexDirection: "row",

    marginBottom: 12,
  },

  secondaryText: {
    marginLeft: 10,

    color:
      SALARY_THEME.colors.primary,

    fontWeight: "700",

    fontSize: 15,
  },

  closeButton: {
    marginTop: 8,

    marginBottom: 24,

    alignItems: "center",
  },

  closeText: {
    color:
      SALARY_THEME.colors.textMuted,

    fontSize: 15,

    fontWeight: "700",
  },
});