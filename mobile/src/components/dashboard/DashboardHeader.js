import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
} from 'react-native';

import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../../store/AuthContext';

export default function DashboardHeader({
  adminName = "Administrator",
  date = "",
  onLogout,
}) {
  const { user } = useAuth();
  const companyName = user?.company || "Enterprise HRMS Platform";

  const hour = new Date().getHours();

  let greeting = "Good Evening";

  if (hour < 12) greeting = "Good Morning";
  else if (hour < 17) greeting = "Good Afternoon";

  return (
    <View style={styles.container}>

      {/* Header */}

      <View style={styles.headerRow}>

        <View style={{flex:1}}>

          <View style={styles.companyBadge}>
            <Ionicons name="business-outline" size={12} color="#1D4ED8" style={{ marginRight: 4 }} />
            <Text style={styles.companyBadgeText}>{companyName.toUpperCase()}</Text>
          </View>

          <Text style={styles.greeting}>
            {greeting}
          </Text>

          <Text style={styles.name}>
            {adminName}
          </Text>

          <Text style={styles.date}>
            {date}
          </Text>

        </View>

        <TouchableOpacity
          activeOpacity={0.85}
          style={styles.logout}
          onPress={onLogout}
        >
          <Ionicons
            name="log-out-outline"
            size={20}
            color="#475569"
          />
        </TouchableOpacity>

      </View>

      {/* Divider */}

      <View style={styles.divider} />

      {/* Footer */}

      <View style={styles.footer}>

        <View style={styles.status}>

          <View style={styles.dot} />

          <Text style={styles.statusText}>
            All systems operational
          </Text>

        </View>

        <View style={styles.timeBox}>

          <Ionicons
            name="time-outline"
            size={14}
            color="#94A3B8"
          />

          <Text style={styles.time}>
            Updated now
          </Text>

        </View>

      </View>

    </View>
  );

}

const styles = StyleSheet.create({

  container:{

    backgroundColor:"#FFFFFF",

    borderRadius:16,

    padding:20,

    marginBottom:18,

    borderWidth:1,

    borderColor:"#E8EDF3",

    shadowColor:"#0F172A",

    shadowOpacity:0.04,

    shadowRadius:10,

    shadowOffset:{
      width:0,
      height:4,
    },

    elevation:2,

  },

  headerRow:{

    flexDirection:"row",

    justifyContent:"space-between",

    alignItems:"flex-start",

  },

  companyBadge:{
    flexDirection:"row",
    alignItems:"center",
    alignSelf:"flex-start",
    backgroundColor:"#EFF6FF",
    borderColor:"#BFDBFE",
    borderWidth:1,
    paddingHorizontal:8,
    paddingVertical:3,
    borderRadius:8,
    marginBottom:6,
  },

  companyBadgeText:{
    fontSize:10,
    fontWeight:"800",
    color:"#1D4ED8",
    letterSpacing:0.6,
  },

  greeting:{

    fontSize:12,

    color:"#64748B",

    fontWeight:"500",

  },

  name:{

    marginTop:2,

    fontSize:20,

    fontWeight:"800",

    color:"#0F172A",

    letterSpacing:-0.4,

  },

  date:{

    marginTop:4,

    fontSize:12,

    color:"#94A3B8",

  },

  logout:{

    width:40,

    height:40,

    borderRadius:12,

    backgroundColor:"#F8FAFC",

    borderWidth:1,

    borderColor:"#E2E8F0",

    justifyContent:"center",

    alignItems:"center",

  },

  divider:{

    height:1,

    backgroundColor:"#EEF2F7",

    marginVertical:18,

  },

  footer:{

    flexDirection:"row",

    justifyContent:"space-between",

    alignItems:"center",

  },

  status:{

    flexDirection:"row",

    alignItems:"center",

  },

  dot:{

    width:8,

    height:8,

    borderRadius:8,

    backgroundColor:"#22C55E",

    marginRight:8,

  },

  statusText:{

    fontSize:12,

    color:"#16A34A",

    fontWeight:"600",

  },

  timeBox:{

    flexDirection:"row",

    alignItems:"center",

  },

  time:{

    marginLeft:5,

    fontSize:12,

    color:"#94A3B8",

    fontWeight:"500",

  },

});