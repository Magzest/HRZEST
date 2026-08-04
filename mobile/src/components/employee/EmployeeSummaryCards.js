import React from "react";
import {
  View,
  Text,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

const CARDS = [

  {
    key: "hours",
    title: "Hours",
    value: "08h 20m",
    subtitle: "Worked Today",
    icon: "time-outline",
    color: "#2563EB",
    bg: "#EEF4FF",
  },

  {
    key: "attendance",
    title: "Attendance",
    value: "98%",
    subtitle: "This Month",
    icon: "calendar-outline",
    color: "#16A34A",
    bg: "#ECFDF5",
  },

  {
    key: "leave",
    title: "Leave",
    value: "08",
    subtitle: "Remaining",
    icon: "leaf-outline",
    color: "#EA580C",
    bg: "#FFF7ED",
  },

  {
    key: "performance",
    title: "Performance",
    value: "A+",
    subtitle: "Overall",
    icon: "trending-up-outline",
    color: "#7C3AED",
    bg: "#F5F3FF",
  },

];

export default function EmployeeSummaryCards({
  hours = "0h 00m",
  attendance = "0%",
  leaveBalance = "0",
  performance = "N/A",
}) {

  const values = {

    hours,

    attendance,

    leave: leaveBalance,

    performance,

  };

  return (

    <View style={styles.container}>

      <Text style={styles.heading}>
        Today's Summary
      </Text>

      <View style={styles.grid}>

        {

          CARDS.map((item) => (

            <View
              key={item.key}
              style={styles.card}
            >

              <View style={styles.topRow}>

                <View
                  style={[
                    styles.iconBox,
                    {
                      backgroundColor: item.bg,
                    },
                  ]}
                >

                  <Ionicons
                    name={item.icon}
                    size={18}
                    color={item.color}
                  />

                </View>

                <Ionicons
                  name="chevron-forward"
                  size={16}
                  color="#CBD5E1"
                />

              </View>

              <Text style={styles.value}>
                {values[item.key]}
              </Text>

              <Text style={styles.title}>
                {item.title}
              </Text>

              <Text style={styles.subtitle}>
                {item.subtitle}
              </Text>

            </View>

          ))

        }

      </View>

    </View>

  );

}

const styles = StyleSheet.create({

  container: {

    marginBottom: 24,

  },

  heading: {

    fontSize: 18,

    fontWeight: "700",

    color: "#0F172A",

    marginBottom: 16,

  },

  grid: {

    flexDirection: "row",

    flexWrap: "wrap",

    justifyContent: "space-between",

  },

  card: {

    width: "48%",

    backgroundColor: "#FFFFFF",

    borderRadius: 20,

    padding: 16,

    marginBottom: 14,

    borderWidth: 1,

    borderColor: "#E8EDF5",

    shadowColor: "#0F172A",

    shadowOpacity: 0.05,

    shadowRadius: 10,

    shadowOffset: {
      width: 0,
      height: 4,
    },

    elevation: 3,

  },

  topRow: {

    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    marginBottom: 14,

  },

  iconBox: {

    width: 42,

    height: 42,

    borderRadius: 12,

    justifyContent: "center",

    alignItems: "center",

  },

  value: {

    fontSize: 24,

    fontWeight: "800",

    color: "#0F172A",

    letterSpacing: -0.5,

  },

  title: {

    marginTop: 6,

    fontSize: 14,

    fontWeight: "700",

    color: "#334155",

  },

  subtitle: {

    marginTop: 4,

    fontSize: 12,

    color: "#94A3B8",

  },

});