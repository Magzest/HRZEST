import React from "react";
import {
  View,
  Text,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

const EVENTS = [

  {
    title: "Company Holiday",
    subtitle: "Independence Day",
    date: "15 Aug",
    icon: "flag-outline",
    color: "#2563EB",
    bg: "#EEF4FF",
  },

  {
    title: "Birthday",
    subtitle: "Sarah Johnson",
    date: "22 Jun",
    icon: "gift-outline",
    color: "#F59E0B",
    bg: "#FFF7ED",
  },

  {
    title: "Team Meeting",
    subtitle: "Engineering Sync",
    date: "Tomorrow",
    icon: "people-outline",
    color: "#16A34A",
    bg: "#ECFDF5",
  },

];

export default function EmployeeUpcomingEvents({
  events = [],
}) {
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>
            Upcoming Events
          </Text>
          <Text style={styles.subtitle}>
            Holidays, events & announcements
          </Text>
        </View>
        <Ionicons name="calendar-outline" size={20} color="#173B8C" />
      </View>

      {events.length === 0 ? (
        <View style={{ backgroundColor: "#FFFFFF", borderRadius: 16, padding: 24, alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: "#E2E8F0" }}>
          <Ionicons name="calendar-outline" size={36} color="#94A3B8" />
          <Text style={{ fontSize: 14, fontWeight: "600", color: "#64748B", marginTop: 8 }}>
            No Upcoming Events Scheduled
          </Text>
        </View>
      ) : (
        events.map((item, index) => (

          <View
            key={index}
            style={styles.card}
          >

            <View
              style={[
                styles.iconBox,
                {
                  backgroundColor:item.bg,
                },
              ]}
            >

              <Ionicons
                name={item.icon}
                size={22}
                color={item.color}
              />

            </View>

            <View style={styles.info}>

              <Text style={styles.eventTitle}>
                {item.title}
              </Text>

              <Text style={styles.eventSubtitle}>
                {item.subtitle}
              </Text>

            </View>

            <View style={styles.dateBox}>

              <Text style={styles.date}>
                {item.date}
              </Text>

            </View>

          </View>

        ))
      )}

    </View>

  );

}

const styles = StyleSheet.create({

  container:{

    backgroundColor:"#FFFFFF",

    borderRadius:22,

    padding:20,

    marginBottom:22,

    borderWidth:1,

    borderColor:"#E8EDF5",

    shadowColor:"#0F172A",

    shadowOpacity:.05,

    shadowRadius:14,

    shadowOffset:{
      width:0,
      height:6,
    },

    elevation:4,

  },

  header:{

    marginBottom:18,

  },

  title:{

    fontSize:18,

    fontWeight:"700",

    color:"#0F172A",

  },

  subtitle:{

    marginTop:4,

    fontSize:13,

    color:"#64748B",

  },

  card:{

    flexDirection:"row",

    alignItems:"center",

    paddingVertical:14,

    borderBottomWidth:1,

    borderBottomColor:"#EEF2F7",

  },

  iconBox:{

    width:48,

    height:48,

    borderRadius:14,

    justifyContent:"center",

    alignItems:"center",

    marginRight:14,

  },

  info:{

    flex:1,

  },

  eventTitle:{

    fontSize:15,

    fontWeight:"700",

    color:"#0F172A",

  },

  eventSubtitle:{

    marginTop:4,

    color:"#64748B",

    fontSize:12,

  },

  dateBox:{

    backgroundColor:"#F8FAFC",

    paddingHorizontal:12,

    paddingVertical:8,

    borderRadius:14,

  },

  date:{

    color:"#173B8C",

    fontWeight:"700",

    fontSize:12,

  },

});